import pytest
from flask import Flask, g

from src.flask_rpbac import RPBAC, Permission, Role


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


def test_memory_cache_is_created_through_rpbac_configuration(app):
    rpbac = RPBAC(app, cache_config={"type": "memory"})

    assert rpbac.cache is not None


def test_unsupported_cache_configuration_is_rejected_by_rpbac(app):
    with pytest.raises(ValueError, match="not a supported type of cache"):
        RPBAC(app, cache_config={"type": "redis"})


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
