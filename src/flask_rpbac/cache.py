"""Hold code thst handles application caching"""

from __future__ import annotations

import atexit
import json
import logging
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from colorama import Fore, Style

if TYPE_CHECKING:
    from flask import Flask

    from . import RPBACBuildContext

logger = logging.getLogger(__name__)


def _import_redis():
    try:
        import redis
    except ImportError:
        raise ImportError(
            "RedisCache requires the 'redis' package. "
            "Install it with: pip install redis or pip install flask_rpbac[redis]"
        )
    return redis


class Cache(Protocol):
    """Cache interface protocol"""

    def get(self, key: str) -> RPBACBuildContext | None: ...
    def set(self, key: str, value: RPBACBuildContext): ...
    def delete(self, key: str): ...


class InMemoryCache:
    """A simple In Memory cache implemetation for storing roles and permissions per user"""

    def __init__(self, **options):
        self.__cache: dict[str, RPBACBuildContext] = {}

        self.__warn()

    def set(self, key: str, value: RPBACBuildContext) -> None:
        """
        Store roles and permission of users

        Args:
            key (str): A unique identity mostly the user id
            value (RPBACBuildContext): A build context containing the users roles and permissions
        """
        self.__cache[key] = value

    def get(self, key: str) -> RPBACBuildContext | None:
        """
        Retrives users role and permissions

        Args:
            key (str): Unique identity mostly user id used in setting or
                storing the data

        Returns:
            RPBACBuildContext | None: A build context if key is present else None
        """
        if key in self.__cache:
            return self.__cache[key]

        return None

    def delete(self, key: str) -> None:
        """
        Removing users roles and permission

        Args:
            key (str): A unique identity mostly the user id
        """
        if key in self.__cache:
            del self.__cache[key]

    def __warn(self):
        message = (
            "Please do not use in-memory cache for production. Substitue with a production"
            " ready cache such as Redis or Memcache"
        )
        print(f"{Fore.YELLOW}WARNING: {message}{Style.RESET_ALL}")


class RedisCache:
    """Redis cache implementation for caching users roles and permissions"""

    def __init__(self, **options):
        self.instance = options.get("instance")
        self.url = options.get("url")
        self.host = options.get("host", "localhost")
        self.port = options.get("port", 6379)
        self.db = options.get("db", 0)
        self.username = options.get("username")
        self.password = options.get("password")
        self.ttl = options.get("ttl")
        self.ping_on_init = options.get("ping_on_init")
        self.app: Flask = options["app"]

        self._socket_timeout = 5.0
        self._socket_connect_timeout = 5.0
        self._decode_responses = True

        self._reconnection_interval = 5.0
        self._is_healthy = True
        self._is_reconnecting = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ping_thread: threading.Thread | None = None

        atexit.register(self.stop)
        self.app.extensions["redis_thread_stop"] = self.stop

        if self.instance is not None:
            self.__client = self.instance
        else:
            self._redis = _import_redis()

            if self.url is not None:
                self._init_redis_from_url()
            else:
                self._init_redis()

        if self.ping_on_init:
            self.__client.ping()

    def get(self, key: str) -> Any | None:
        """
        Retrives users role and permissions

        Args:
            key (str): Unique identity mostly user id used in setting or
                storing the data

        Returns:
            RPBACBuildContext | None: A build context if key is present else None
        """
        if not self._is_healthy:
            return None

        try:
            data = self.__client.get(self.__key(key))
        except self._redis.RedisError as e:
            logger.error(f"{Fore.RED}Redis Error: {e}{Style.RESET_ALL}")
            self._on_failure()

            return None

        if data is not None:
            try:
                from . import RPBACBuildContext

                return RPBACBuildContext(**json.loads(data))
            except (json.JSONDecodeError, TypeError, ValueError):
                self.delete(key)

        return None

    def set(self, key: str, value: RPBACBuildContext):
        """
        Store roles and permission of users

        Args:
            key (str): A unique identity mostly the user id
            value (RPBACBuildContext): A build context containing the users roles and permissions
        """
        if not self._is_healthy:
            return

        _value = json.dumps(
            {
                "roles": list(value.roles),
                "permissions": list(value.permissions),
                "kwargs": value.kwargs,
            }
        )

        try:
            self.__client.set(self.__key(key), _value, ex=self.ttl)
        except self._redis.RedisError as e:
            logger.error(f"{Fore.RED}Redis Error: {e}{Style.RESET_ALL}")
            self._on_failure()

            return

    def delete(self, key: str):
        """
        Removing users roles and permission

        Args:
            key (str): A unique identity mostly the user id
        """
        if not self._is_healthy:
            return

        try:
            self.__client.delete(self.__key(key))
        except self._redis.RedisError as e:
            logger.error(f"{Fore.RED}Redis Error: {e}{Style.RESET_ALL}")
            self._on_failure()

            return

    # Helper methods

    def _init_redis(self) -> None:
        """Initialize a new redis client"""
        self.__client = self._redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            username=self.username,
            decode_responses=self._decode_responses,
            socket_timeout=self._socket_timeout,
            socket_connect_timeout=self._socket_connect_timeout,
        )

    def _init_redis_from_url(self) -> None:
        """Initialize a new redis client from url"""
        self.__client = self._redis.from_url(
            self.url,  # pyright: ignore
            decode_responses=self._decode_responses,
            socket_timeout=self._socket_timeout,
            socket_connect_timeout=self._socket_connect_timeout,
        )

    def __key(self, key: str) -> str:
        """To avoid name conflict issue, the package name is used as a prefix to the key"""
        return f"flask_rpbac:{key}"

    def _on_failure(self):
        """This is called when redis fails. Flips the flags and start reconnection recovery"""
        with self._lock:
            if self._is_reconnecting:
                return

            if not self._is_healthy:
                return

            self._is_healthy = False
            self._is_reconnecting = True

        t = threading.Thread(
            target=self._reconnection_loop, name="RedisCache-reconnect", daemon=True
        )

        logger.info(
            f"{Fore.CYAN}INFO: Redis starts reconnection loop.{Style.RESET_ALL}"
        )
        self._ping_thread = t
        t.start()

    def _reconnection_loop(self):
        """This pings redis every 5 seconds to see if it is back online and flips the flags appropriately"""
        while not self._stop.is_set():
            if self._ping():
                with self._lock:
                    self._is_healthy = True
                    self._is_reconnecting = False

                logger.info(f"{Fore.GREEN}INFO: Redis is reconnected.{Style.RESET_ALL}")
                return

            self._stop.wait(self._reconnection_interval)

        # The self.stop() was called, clean up state.
        with self._lock:
            self._is_reconnecting = False

    def _ping(self):
        """Pings redis and returns True if it is reachable else False"""
        try:
            return bool(self.__client.ping())
        except self._redis.RedisError:
            return False

    def stop(self, timeout: float = 5.0):
        """A kill switch to clean up thread processes while it is still running.

        Args:
            timeout (float, optional): The max time stop() waits for the
                reconnect thread to actually finish after signalling it. Defaults to 5.0.
        """
        if self._stop.is_set():
            return

        self._stop.set()
        atexit.unregister(self.stop)

        t = self._ping_thread

        if t is not None and t.is_alive():
            t.join(timeout=float(timeout))


@dataclass
class CacheConfig:
    type: str
    app: Flask
    url: str | None = None
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    username: str | None = None
    password: str | None = None
    instance: Any = None
    ttl: int = 300
    ping_on_init: bool = True


class CacheFactory:
    """A class that creates a type of cache"""

    def __init__(self, config: CacheConfig) -> None:
        self.type = config.type
        self.url = config.url
        self.host = config.host
        self.port = config.port
        self.db = config.db
        self.username = config.username
        self.password = config.password
        self.ttl = config.ttl
        self.instance = config.instance
        self.ping_on_init = config.ping_on_init
        self.app = config.app

        self.__caches = {"memory": InMemoryCache, "redis": RedisCache}

    def create(self) -> Cache:
        """Creates a cache using the type of the cache"""
        if self.type in self.__caches:
            return self.__caches[self.type](
                url=self.url,
                host=self.host,
                port=self.port,
                db=self.db,
                username=self.username,
                password=self.password,
                ttl=self.ttl,
                instance=self.instance,
                ping_on_init=self.ping_on_init,
                app=self.app,
            )
        raise ValueError(f"{self.type} is not a supported type of cache")
