import pytest
from flask import Blueprint, Flask

from src.flask_rpbac import RPBAC, All, Not, Permission, Predicate, Role
from src.flask_rpbac.exc import (
    RPBACError,
    RPBACPermissionError,
    RPBACPredicateError,
    RPBACRoleError,
)


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    yield app

    stop_reconnect_thread = app.extensions.get("redis_thread_stop")
    if stop_reconnect_thread is not None:
        stop_reconnect_thread()


@pytest.fixture
def client(app):
    return app.test_client()


def test_async_route_with_sync_loaders_is_authorized(app, client):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def load_roles():
        return ["admin"]

    @rpbac.permission_loader
    def load_permissions():
        return ["post:read"]

    @app.get("/async-sync-loaders")
    @rpbac.required(All(Role("admin"), Permission("post:read")))
    async def async_sync_loaders():
        return {"status": "allowed"}

    response = client.get("/async-sync-loaders")

    assert response.status_code == 200
    assert response.get_json() == {"status": "allowed"}


@pytest.mark.parametrize("requirement", [Role("admin"), Permission("post:read")])
def test_async_route_denies_missing_role_or_permission(app, client, requirement):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    async def load_roles():
        return []

    @rpbac.permission_loader
    async def load_permissions():
        return []

    @app.get("/async-denied")
    @rpbac.required(requirement)
    async def async_denied():
        return "should not execute"

    response = client.get("/async-denied")

    assert response.status_code == 403
    assert response.get_json()["error"] == "forbidden"


def test_async_loader_callbacks_are_awaited(app, client):
    rpbac = RPBAC(app)
    calls = []

    @rpbac.role_loader
    async def load_roles():
        calls.append("roles")
        return ["editor"]

    @rpbac.permission_loader
    async def load_permissions():
        calls.append("permissions")
        return ["post:write"]

    @app.get("/async-loaders")
    @rpbac.required(All(Role("editor"), Permission("post:write")))
    async def async_loaders():
        return "ok"

    response = client.get("/async-loaders")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ok"
    assert calls == ["roles", "permissions"]


def test_async_user_data_loader_is_awaited(app, client):
    rpbac = RPBAC(app)
    calls = []

    @rpbac.user_data_loader
    async def load_user_data():
        calls.append("user-data")
        return {"roles": ["admin"], "permissions": ["post:read"]}

    @app.get("/async-user-data")
    @rpbac.required(Role("admin") & Permission("post:read"))
    async def async_user_data():
        return "ok"

    response = client.get("/async-user-data")

    assert response.status_code == 200
    assert calls == ["user-data"]


def test_async_user_data_loader_is_cached_with_async_identity(app, client):
    rpbac = RPBAC(app, cache_config={"type": "memory"})
    calls = {"identity": 0, "user-data": 0}

    @rpbac.load_user_identity
    async def load_identity():
        calls["identity"] += 1
        return "user-async"

    @rpbac.user_data_loader
    async def load_user_data():
        calls["user-data"] += 1
        return {"roles": ["admin"], "permissions": ["post:read"]}

    @app.get("/async-combined-cache")
    @rpbac.required(Role("admin") & Permission("post:read"))
    async def async_combined_cache():
        return "ok"

    assert client.get("/async-combined-cache").status_code == 200
    assert client.get("/async-combined-cache").status_code == 200
    assert calls == {"identity": 2, "user-data": 1}


def test_async_cache_hit_uses_current_route_kwargs(app, client):
    rpbac = RPBAC(app, cache_config={"type": "memory"})
    loader_calls = []

    @rpbac.load_user_identity
    async def load_identity():
        return "user-with-items"

    @rpbac.role_loader
    async def load_roles():
        loader_calls.append("roles")
        return ["editor"]

    def may_edit(ctx):
        return ctx.kwargs["item_id"] % 2 == 0

    @app.get("/async-cached-items/<int:item_id>")
    @rpbac.role_required(Role("editor"))
    @rpbac.required(Predicate(may_edit))
    async def async_cached_item(item_id):
        return {"item_id": item_id}

    assert client.get("/async-cached-items/2").status_code == 200
    assert client.get("/async-cached-items/4").status_code == 200
    denied = client.get("/async-cached-items/3")

    assert denied.status_code == 403
    assert loader_calls == ["roles"]


def test_async_multiple_route_checks_reuse_request_context(app, client):
    rpbac = RPBAC(app)
    calls = {"roles": 0, "permissions": 0}

    @rpbac.role_loader
    async def load_roles():
        calls["roles"] += 1
        return ["editor"]

    @rpbac.permission_loader
    async def load_permissions():
        calls["permissions"] += 1
        return ["post:read"]

    @app.get("/async-stacked-checks")
    @rpbac.role_required(Role("editor"))
    @rpbac.permission_required(Permission("post:read"))
    async def async_stacked_checks():
        return "ok"

    response = client.get("/async-stacked-checks")

    assert response.status_code == 200
    assert calls == {"roles": 1, "permissions": 1}


def test_async_identity_loader_and_memory_cache_are_reused(app, client):
    rpbac = RPBAC(app, cache_config={"type": "memory"})
    calls = {"identity": 0, "roles": 0}

    @rpbac.load_user_identity
    async def load_identity():
        calls["identity"] += 1
        return "user-1"

    @rpbac.role_loader
    async def load_roles():
        calls["roles"] += 1
        return ["admin"]

    @app.get("/async-cache")
    @rpbac.role_required(Role("admin"))
    async def async_cache():
        return "ok"

    assert client.get("/async-cache").status_code == 200
    assert client.get("/async-cache").status_code == 200
    assert calls == {"identity": 2, "roles": 1}


def test_async_identity_loader_returns_none_without_cache_key(app, client):
    rpbac = RPBAC(app, cache_config={"type": "memory"})
    calls = {"identity": 0, "roles": 0}

    @rpbac.load_user_identity
    async def load_identity():
        calls["identity"] += 1

    @rpbac.role_loader
    async def load_roles():
        calls["roles"] += 1
        return ["admin"]

    @app.get("/async-no-identity")
    @rpbac.role_required(Role("admin"))
    async def async_no_identity():
        return "ok"

    assert client.get("/async-no-identity").status_code == 200
    assert client.get("/async-no-identity").status_code == 200
    assert calls == {"identity": 2, "roles": 2}


def test_async_route_rejection_hook_receives_rpbac_error(app, client):
    received = []

    def rejection_hook(error):
        received.append(error)
        return {"handled": True, "error": str(error)}, 418

    rpbac = RPBAC(app, rejection_hook=rejection_hook)

    @rpbac.role_loader
    async def load_roles():
        return []

    @app.get("/async-hook")
    @rpbac.role_required(Role("admin"))
    async def async_hook():
        return "ok"

    response = client.get("/async-hook")

    assert response.status_code == 418
    assert response.get_json()["handled"] is True
    assert isinstance(received[0], RPBACRoleError)


def test_async_route_generic_errors_can_be_handled_by_flask(app, client):
    rpbac = RPBAC(app, raise_generic_error=True)

    @rpbac.role_loader
    async def load_roles():
        return []

    @app.errorhandler(RPBACError)
    def handle_error(error):
        return {"handled": True, "message": str(error)}, 409

    @app.get("/async-generic-error")
    @rpbac.role_required(Role("admin"))
    async def async_generic_error():
        return "ok"

    response = client.get("/async-generic-error")

    assert response.status_code == 409
    assert response.get_json()["handled"] is True


def test_async_route_predicate_receives_route_kwargs(app, client):
    rpbac = RPBAC(app)

    def can_access(ctx):
        return ctx.kwargs["item_id"] == 7

    @app.get("/async-items/<int:item_id>")
    @rpbac.required(Predicate(can_access))
    async def async_item(item_id):
        return {"item_id": item_id}

    assert client.get("/async-items/7").status_code == 200
    assert client.get("/async-items/8").status_code == 403


def test_async_predicate_receives_context_and_is_awaited(app, client):
    rpbac = RPBAC(app)
    predicate_calls = []

    @rpbac.role_loader
    async def load_roles():
        return ["editor"]

    @rpbac.permission_loader
    async def load_permissions():
        return ["post:write"]

    async def can_edit(ctx):
        predicate_calls.append(ctx)
        return (
            ctx.kwargs == {"post_id": 42}
            and set(ctx.roles) == {"editor"}
            and set(ctx.permissions) == {"post:write"}
        )

    @app.get("/async-predicate/posts/<int:post_id>")
    @rpbac.required(Predicate(can_edit))
    async def async_predicate_post(post_id):
        return {"post_id": post_id}

    response = client.get("/async-predicate/posts/42")

    assert response.status_code == 200
    assert response.get_json() == {"post_id": 42}
    assert len(predicate_calls) == 1
    assert predicate_calls[0].kwargs == {"post_id": 42}


@pytest.mark.parametrize("predicate_result", [False, None, 0, ""])
def test_async_predicate_false_results_raise_structured_forbidden_error(
    app, client, predicate_result
):
    rpbac = RPBAC(app, raise_generic_error=True)
    predicate_calls = []

    async def deny(ctx):
        predicate_calls.append(ctx)
        return predicate_result

    predicate = Predicate(deny)

    @app.get("/async-predicate-denied/<int:item_id>")
    @rpbac.required(predicate)
    async def async_predicate_denied(item_id):
        return "unreachable"

    with pytest.raises(RPBACPredicateError) as raised:
        client.get("/async-predicate-denied/19")

    assert raised.value.func is deny
    assert raised.value.ctx.kwargs == {"item_id": 19}
    assert predicate_calls == [raised.value.ctx]


def test_async_predicate_exception_propagates_without_wrapping(app, client):
    rpbac = RPBAC(app, raise_generic_error=True)

    async def broken_predicate(ctx):
        raise LookupError(f"item {ctx.kwargs['item_id']} is unavailable")

    @app.get("/async-predicate-exception/<int:item_id>")
    @rpbac.required(Predicate(broken_predicate))
    async def async_predicate_exception(item_id):
        return "unreachable"

    with pytest.raises(LookupError, match="item 8 is unavailable"):
        client.get("/async-predicate-exception/8")


def test_async_blueprint_predicate_receives_kwargs_and_handles_denial(app, client):
    rpbac = RPBAC(app)
    blueprint = Blueprint("async_predicate_bp", __name__)
    calls = []

    async def owns_record(ctx):
        calls.append(ctx.kwargs["record_id"])
        return ctx.kwargs["record_id"] == 5

    rpbac.protect_blueprint(blueprint, Predicate(owns_record))

    @blueprint.get("/<int:record_id>")
    async def record(record_id):
        return {"record_id": record_id}

    app.register_blueprint(blueprint, url_prefix="/async-predicate-records")

    allowed = client.get("/async-predicate-records/5")
    denied = client.get("/async-predicate-records/6")

    assert allowed.status_code == 200
    assert allowed.get_json() == {"record_id": 5}
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "forbidden"
    assert "Authz Failed" in denied.get_json()["message"]
    assert calls == [5, 6]


def test_async_blueprint_route_uses_async_loaders(app, client):
    rpbac = RPBAC(app)
    blueprint = Blueprint("async_admin", __name__)

    @rpbac.role_loader
    async def load_roles():
        return ["admin"]

    rpbac.protect_blueprint(blueprint, Role("admin"))

    @blueprint.get("/dashboard")
    async def dashboard():
        return "dashboard"

    app.register_blueprint(blueprint, url_prefix="/admin")

    response = client.get("/admin/dashboard")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "dashboard"


def test_async_blueprint_route_level_and_blueprint_rules_are_combined(app, client):
    rpbac = RPBAC(app)
    blueprint = Blueprint("async_editor", __name__)

    @rpbac.role_loader
    async def load_roles():
        return ["editor"]

    @rpbac.permission_loader
    async def load_permissions():
        return ["post:read"]

    rpbac.protect_blueprint(blueprint, Role("editor"))

    @blueprint.get("/posts")
    @rpbac.permission_required(Permission("post:read"))
    async def posts():
        return "posts"

    app.register_blueprint(blueprint, url_prefix="/editor")

    response = client.get("/editor/posts")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "posts"


def test_async_route_supports_mixed_sync_and_async_loaders(app, client):
    rpbac = RPBAC(app)
    calls = []

    @rpbac.role_loader
    async def load_roles():
        calls.append("async-role")
        return ["editor"]

    @rpbac.permission_loader
    def load_permissions():
        calls.append("sync-permission")
        return ["post:write"]

    @app.get("/async-mixed-loaders")
    @rpbac.required(Role("editor") & Permission("post:write"))
    async def async_mixed_loaders():
        return "ok"

    response = client.get("/async-mixed-loaders")

    assert response.status_code == 200
    assert calls == ["async-role", "sync-permission"]


def test_async_permission_denial_preserves_specific_error(app, client):
    rpbac = RPBAC(app, raise_generic_error=True)

    @rpbac.permission_loader
    async def load_permissions():
        return []

    @app.get("/async-specific-permission-error")
    @rpbac.permission_required(Permission("post:publish"))
    async def async_specific_permission_error():
        return "unreachable"

    with pytest.raises(RPBACPermissionError):
        client.get("/async-specific-permission-error")


def test_async_not_requirement_allows_user_without_role(app, client):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    async def load_roles():
        return ["reader"]

    @app.get("/async-not-admin")
    @rpbac.required(Not(Role("admin")))
    async def async_not_admin():
        return "allowed"

    response = client.get("/async-not-admin")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "allowed"


def test_async_blueprint_denial_uses_rejection_hook(app, client):
    received = []

    def rejection_hook(error):
        received.append(error)
        return {"denied": True}, 418

    rpbac = RPBAC(app, rejection_hook=rejection_hook)
    blueprint = Blueprint("async_denied_bp", __name__)

    @rpbac.role_loader
    async def load_roles():
        return ["reader"]

    rpbac.protect_blueprint(blueprint, Role("admin"))

    @blueprint.get("/private")
    async def private_route():
        return "unreachable"

    app.register_blueprint(blueprint, url_prefix="/async-denied")
    response = client.get("/async-denied/private")

    assert response.status_code == 418
    assert response.get_json() == {"denied": True}
    assert isinstance(received[0], RPBACRoleError)


def test_async_blueprint_denial_uses_default_flask_error_response(app, client):
    rpbac = RPBAC(app)
    blueprint = Blueprint("async_default_denied_bp", __name__)

    @rpbac.permission_loader
    async def load_permissions():
        return []

    rpbac.protect_blueprint(blueprint, Permission("post:publish"))

    @blueprint.get("/publish")
    async def publish_route():
        return "unreachable"

    app.register_blueprint(blueprint, url_prefix="/async-default-denied")
    response = client.get("/async-default-denied/publish")

    assert response.status_code == 403
    assert response.get_json()["error"] == "forbidden"
    assert "Missing permission" in response.get_json()["message"]


def test_async_blueprint_generic_error_uses_app_error_handler(app, client):
    rpbac = RPBAC(app, raise_generic_error=True)
    blueprint = Blueprint("async_generic_bp", __name__)

    @rpbac.role_loader
    async def load_roles():
        return []

    @app.errorhandler(RPBACError)
    def handle_rpbac_error(error):
        return {"handled": True, "message": str(error)}, 409

    rpbac.protect_blueprint(blueprint, Role("admin"))

    @blueprint.get("/admin")
    async def admin_route():
        return "unreachable"

    app.register_blueprint(blueprint, url_prefix="/async-generic")
    response = client.get("/async-generic/admin")

    assert response.status_code == 409
    assert response.get_json()["handled"] is True
