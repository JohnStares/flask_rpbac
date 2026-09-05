"""Hold code thst handles application caching"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from colorama import Fore, Style

if TYPE_CHECKING:
    from . import RPBACBuildContext


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


@dataclass
class CacheConfig:
    type: str
    url: str = "localhost"
    port: int = 6379
    host: str | None = None
    db: int = 0
    password: str | None = None
    decode_responses: bool = False


class CacheFactory:
    """A class that creates a type of cache"""

    def __init__(self, config: CacheConfig) -> None:
        self.type = config.type
        self.url = config.url
        self.host = config.host
        self.port = config.port
        self.db = config.db
        self.decode_responses = config.decode_responses

        self.__caches = {"memory": InMemoryCache}

    def create(self) -> Cache:
        """Creates a cache using the type of the cache"""
        if self.type in self.__caches:
            return self.__caches[self.type](
                url=self.url,
                host=self.host,
                port=self.port,
                db=self.db,
                decode_reponses=self.decode_responses,
            )
        raise ValueError(f"{self.type} is not a supported type of cache")
