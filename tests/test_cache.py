import builtins
import json
import sys

import pytest
from flask import Flask, g

from src.flask_rpbac import RPBAC, Permission, Role


class FakeRedis:
    redis_calls = []
    url_calls = []

    @classmethod
    def Redis(cls, **options):
        cls.redis_calls.append(options)
        return cls()

    @classmethod
    def from_url(cls, url, **options):
        cls.url_calls.append((url, options))
        return cls()

    def __init__(self):
        self.values = {}
        self.set_calls = []
        self.deleted_keys = []
        self.ping_calls = 0

    def ping(self):
        self.ping_calls += 1
        return True

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self.set_calls.append((key, value, ex))
        self.values[key] = value
        return True

    def delete(self, key):
        self.deleted_keys.append(key)
        self.values.pop(key, None)
        return 1


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


def test_memory_cache_is_created_through_rpbac_configuration(app):
    rpbac = RPBAC(app, cache_config={"type": "memory"})

    assert rpbac.cache is not None


def test_memory_cache_warns_that_it_is_not_for_production(app, capsys):
    RPBAC(app, cache_config={"type": "memory"})

    output = capsys.readouterr().out
    assert "do not use in-memory cache for production" in output


def test_unsupported_cache_configuration_is_rejected_by_rpbac(app):
    with pytest.raises(ValueError, match="not a supported type of cache"):
        RPBAC(app, cache_config={"type": "unsupported"})


def test_redis_cache_is_created_through_rpbac_with_an_injected_client(app):
    redis = FakeRedis()
    rpbac = RPBAC(
        app,
        cache_config={
            "type": "redis",
            "instance": redis,
            "ping_on_init": True,
        },
    )

    assert rpbac.cache is not None
    assert redis.ping_calls == 1


def test_redis_type_uses_default_redis_client_constructor(app, monkeypatch):
    FakeRedis.redis_calls.clear()
    monkeypatch.setitem(sys.modules, "redis", FakeRedis)

    rpbac = RPBAC(
        app,
        cache_config={
            "type": "redis",
            "host": "redis.example",
            "port": 6380,
            "db": 2,
            "username": "app",
            "password": "secret",
            "ping_on_init": True,
        },
    )

    assert rpbac.cache is not None
    assert FakeRedis.redis_calls == [
        {
            "host": "redis.example",
            "port": 6380,
            "db": 2,
            "password": "secret",
            "username": "app",
            "decode_responses": True,
            "socket_timeout": 5.0,
            "socket_connect_timeout": 5.0,
        }
    ]


def test_redis_type_uses_url_constructor(app, monkeypatch):
    FakeRedis.url_calls.clear()
    monkeypatch.setitem(sys.modules, "redis", FakeRedis)

    rpbac = RPBAC(
        app,
        cache_config={
            "type": "redis",
            "url": "redis://redis.example:6380/2",
            "ping_on_init": False,
        },
    )

    assert rpbac.cache is not None
    assert FakeRedis.url_calls == [
        (
            "redis://redis.example:6380/2",
            {
                "decode_responses": True,
                "socket_timeout": 5.0,
                "socket_connect_timeout": 5.0,
            },
        )
    ]


def test_redis_configuration_reports_missing_optional_dependency(app, monkeypatch):
    original_import = builtins.__import__

    def import_without_redis(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("redis is unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_redis)

    with pytest.raises(ImportError, match="RedisCache requires the 'redis' package"):
        RPBAC(app, cache_config={"type": "redis", "ping_on_init": False})


def test_redis_ping_failure_is_propagated_during_rpbac_setup(app):
    class PingFailureRedis(FakeRedis):
        def ping(self):
            raise ConnectionError("Redis is unavailable")

    with pytest.raises(ConnectionError, match="Redis is unavailable"):
        RPBAC(
            app,
            cache_config={
                "type": "redis",
                "instance": PingFailureRedis(),
                "ping_on_init": True,
            },
        )


def test_redis_cache_round_trips_roles_permissions_and_ttl_through_rpbac(app):
    redis = FakeRedis()
    rpbac = RPBAC(
        app,
        cache_config={"type": "redis", "instance": redis, "ttl": 45},
    )
    current_user = {"id": "user-1"}
    calls = {"roles": 0, "permissions": 0}

    @rpbac.load_user_identity
    def load_identity():
        return current_user["id"]

    @rpbac.role_loader
    def load_roles():
        calls["roles"] += 1
        return ["admin"]

    @rpbac.permission_loader
    def load_permissions():
        calls["permissions"] += 1
        return ["post:read"]

    @app.route("/redis-protected")
    @rpbac.required(Role("admin") & Permission("post:read"))
    def redis_protected():
        return "ok"

    client = app.test_client()
    assert client.get("/redis-protected").status_code == 200
    assert client.get("/redis-protected").status_code == 200

    assert calls == {"roles": 1, "permissions": 1}
    key, payload, ttl = redis.set_calls[0]
    assert key
    assert ttl == 45
    assert json.loads(payload) == {
        "roles": ["admin"],
        "permissions": ["post:read"],
        "kwargs": {},
    }


def test_redis_cache_can_be_disabled_from_initial_ping(app):
    redis = FakeRedis()
    RPBAC(
        app,
        cache_config={
            "type": "redis",
            "instance": redis,
            "ping_on_init": False,
        },
    )

    assert redis.ping_calls == 0


def test_redis_cache_malformed_payload_is_deleted_and_reloaded(app):
    redis = FakeRedis()
    redis.values["flask_rpbac:user-1"] = "not-json"
    rpbac = RPBAC(
        app,
        cache_config={"type": "redis", "instance": redis},
    )
    calls = {"roles": 0}

    @rpbac.load_user_identity
    def load_identity():
        return "user-1"

    @rpbac.role_loader
    def load_roles():
        calls["roles"] += 1
        return ["admin"]

    @app.route("/redis-reload")
    @rpbac.role_required(Role("admin"))
    def redis_reload():
        return "ok"

    assert app.test_client().get("/redis-reload").status_code == 200
    assert redis.deleted_keys == ["flask_rpbac:user-1"]
    assert calls["roles"] == 1


def test_redis_cache_payload_with_missing_context_fields_is_reloaded(app):
    redis = FakeRedis()
    redis.values["flask_rpbac:user-1"] = json.dumps(
        {
            "roles": ["admin"],
            "permissions": ["post:read"],
            "unexpected": True,
        }
    )
    rpbac = RPBAC(
        app,
        cache_config={"type": "redis", "instance": redis},
    )
    calls = {"roles": 0, "permissions": 0}

    @rpbac.load_user_identity
    def load_identity():
        return "user-1"

    @rpbac.role_loader
    def load_roles():
        calls["roles"] += 1
        return ["admin"]

    @rpbac.permission_loader
    def load_permissions():
        calls["permissions"] += 1
        return ["post:read"]

    @app.route("/redis-missing-fields")
    @rpbac.required(Role("admin") & Permission("post:read"))
    def redis_missing_fields():
        return "ok"

    assert app.test_client().get("/redis-missing-fields").status_code == 200
    assert redis.deleted_keys == ["flask_rpbac:user-1"]
    assert calls == {"roles": 1, "permissions": 1}


def test_redis_cache_json_scalar_payload_is_reloaded(app):
    redis = FakeRedis()
    redis.values["flask_rpbac:user-1"] = json.dumps(["not", "a", "context"])
    rpbac = RPBAC(
        app,
        cache_config={"type": "redis", "instance": redis},
    )
    calls = {"roles": 0}

    @rpbac.load_user_identity
    def load_identity():
        return "user-1"

    @rpbac.role_loader
    def load_roles():
        calls["roles"] += 1
        return ["admin"]

    @app.route("/redis-invalid-shape")
    @rpbac.role_required(Role("admin"))
    def redis_invalid_shape():
        return "ok"

    assert app.test_client().get("/redis-invalid-shape").status_code == 200
    assert calls["roles"] == 1


def test_redis_cache_keeps_different_user_identities_isolated(app):
    redis = FakeRedis()
    rpbac = RPBAC(
        app,
        cache_config={"type": "redis", "instance": redis},
    )
    current_user = {"id": "user-1", "roles": ["admin"]}
    calls = {"roles": 0}

    @rpbac.load_user_identity
    def load_identity():
        return current_user["id"]

    @rpbac.role_loader
    def load_roles():
        calls["roles"] += 1
        return current_user["roles"]

    @app.route("/redis-users")
    @rpbac.role_required(Role("admin"))
    def redis_users():
        return "ok"

    client = app.test_client()
    assert client.get("/redis-users").status_code == 200
    current_user.update(id="user-2", roles=["editor"])
    assert client.get("/redis-users").status_code == 403
    current_user.update(id="user-1", roles=[])
    assert client.get("/redis-users").status_code == 200

    assert calls["roles"] == 2
    assert set(redis.values) == {"flask_rpbac:user-1", "flask_rpbac:user-2"}


def test_rpbac_without_cache_configuration_does_not_create_cache(app):
    rpbac = RPBAC(app)

    assert rpbac.cache is None


def test_cache_configuration_can_be_applied_during_later_app_initialization():
    rpbac = RPBAC()
    app = Flask(__name__)

    rpbac.init_app(app, cache_config={"type": "memory"})

    assert rpbac.cache is not None


def test_identity_decorator_returns_original_function(app):
    rpbac = RPBAC(app, cache_config={"type": "memory"})

    def identity():
        return "user-1"

    registered = rpbac.load_user_identity(identity)

    assert registered is identity
    assert rpbac.cache is not None


def test_identity_loader_is_not_called_when_cache_is_disabled(app):
    rpbac = RPBAC(app)
    calls = {"identity": 0, "roles": 0}

    @rpbac.load_user_identity
    def load_identity():
        calls["identity"] += 1
        return "user-1"

    @rpbac.role_loader
    def load_roles():
        calls["roles"] += 1
        return ["admin"]

    @app.route("/without-cache")
    @rpbac.role_required(Role("admin"))
    def without_cache():
        return "ok"

    client = app.test_client()
    assert client.get("/without-cache").status_code == 200
    assert client.get("/without-cache").status_code == 200
    assert calls == {"identity": 0, "roles": 2}


def test_cache_hit_skips_role_and_permission_loaders_between_requests(app):
    rpbac = RPBAC(app, cache_config={"type": "memory"})
    calls = {"identity": 0, "roles": 0, "permissions": 0}
    current_user = {"id": "user-1"}

    @rpbac.load_user_identity
    def load_identity():
        calls["identity"] += 1
        return current_user["id"]

    @rpbac.role_loader
    def load_roles():
        calls["roles"] += 1
        return ["admin"]

    @rpbac.permission_loader
    def load_permissions():
        calls["permissions"] += 1
        return ["post:read"]

    @app.route("/protected")
    @rpbac.required(Role("admin") & Permission("post:read"))
    def protected():
        return "ok"

    client = app.test_client()
    assert client.get("/protected").status_code == 200
    assert client.get("/protected").status_code == 200

    assert calls == {"identity": 2, "roles": 1, "permissions": 1}


def test_cache_miss_loads_new_user_and_keeps_users_isolated(app):
    rpbac = RPBAC(app, cache_config={"type": "memory"})
    current_user = {"id": "user-1", "roles": ["admin"], "permissions": []}
    calls = {"identity": 0, "roles": 0}

    @rpbac.load_user_identity
    def load_identity():
        calls["identity"] += 1
        return current_user["id"]

    @rpbac.role_loader
    def load_roles():
        calls["roles"] += 1
        return current_user["roles"]

    @app.route("/admin")
    @rpbac.role_required(Role("admin"))
    def admin():
        return "ok"

    client = app.test_client()
    assert client.get("/admin").status_code == 200

    current_user.update(id="user-2", roles=["editor"])
    assert client.get("/admin").status_code == 403

    current_user.update(id="user-1", roles=[])
    assert client.get("/admin").status_code == 200
    assert calls == {"identity": 3, "roles": 2}


def test_none_identity_disables_effective_cache_key(app):
    rpbac = RPBAC(app, cache_config={"type": "memory"})
    calls = {"roles": 0}

    @rpbac.load_user_identity
    def load_identity():
        return None

    @rpbac.role_loader
    def load_roles():
        calls["roles"] += 1
        return ["admin"]

    @app.route("/anonymous")
    @rpbac.role_required(Role("admin"))
    def anonymous():
        return "ok"

    client = app.test_client()
    assert client.get("/anonymous").status_code == 200
    assert client.get("/anonymous").status_code == 200
    assert calls["roles"] == 2


def test_identity_is_called_once_per_request_context(app):
    rpbac = RPBAC(app, cache_config={"type": "memory"})
    calls = {"identity": 0, "roles": 0}

    @rpbac.load_user_identity
    def load_identity():
        calls["identity"] += 1
        return "user-1"

    @rpbac.role_loader
    def load_roles():
        calls["roles"] += 1
        return ["admin"]

    @app.route("/multiple-checks")
    @rpbac.role_required(Role("admin"))
    @rpbac.permission_required(Permission("post:read"))
    def multiple_checks():
        return "ok"

    @rpbac.permission_loader
    def load_permissions():
        return ["post:read"]

    with app.test_request_context("/multiple-checks"):
        assert multiple_checks() == "ok"
        assert hasattr(g, "_rpbac_context")

    assert calls == {"identity": 1, "roles": 1}


def test_user_data_loader_is_cached_by_identity_between_requests(app):
    rpbac = RPBAC(app, cache_config={"type": "memory"})
    current_user = {"id": "user-1", "roles": ["admin"], "permissions": ["post:read"]}
    calls = {"identity": 0, "user_data": 0}

    @rpbac.load_user_identity
    def load_identity():
        calls["identity"] += 1
        return current_user["id"]

    @rpbac.user_data_loader
    def load_user_data():
        calls["user_data"] += 1
        return {
            "id": current_user["id"],
            "roles": current_user["roles"],
            "permissions": current_user["permissions"],
        }

    @app.route("/combined-loader")
    @rpbac.required(Role("admin") & Permission("post:read"))
    def combined_loader():
        return "ok"

    client = app.test_client()
    assert client.get("/combined-loader").status_code == 200
    current_user["roles"] = []
    current_user["permissions"] = []
    assert client.get("/combined-loader").status_code == 200

    assert calls == {"identity": 2, "user_data": 1}
