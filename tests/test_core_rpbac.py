import pytest
from flask import Flask

from src.flask_rpbac import RPBAC, All, Any, Permission, Role
from src.flask_rpbac.exc import RPBACError, RPBACPermissionError, RPBACRoleError


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_rpbac_requires_initialized_app_for_protected_routes():
    rpbac = RPBAC()

    with pytest.raises(
        AssertionError, match="Please initialize your application into flask RPBAC"
    ):
        rpbac.role_required(Role("Admin"))(lambda: "ok")()


def test_rpbac_error_types_are_raised_for_missing_permission_or_role(app):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def role_loader():
        return ["Editor"]

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read"]

    with pytest.raises(RPBACPermissionError), app.test_request_context():
        rpbac.required(Permission("post:delete"))(lambda: "ok")()

    with pytest.raises(RPBACRoleError), app.test_request_context():
        rpbac.required(Role("Admin"))(lambda: "ok")()

    with pytest.raises(RPBACError), app.test_request_context():
        rpbac.required(Permission("post:delete"))(lambda: "ok")()


def test_role_and_permission_decorators_handle_real_flask_requests(app, client):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def role_loader():
        return ["Editor"]

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read"]

    @app.route("/admin")
    @rpbac.role_required(Role("Admin"))
    def admin_route():
        return "ok"

    @app.route("/post")
    @rpbac.permission_required(Permission("post:delete"))
    def post_route():
        return "ok"

    assert client.get("/admin").status_code == 403
    assert client.get("/post").status_code == 403


def test_default_rpbac_error_handler_returns_json_for_denied_route(app, client):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def role_loader():
        return []

    @app.route("/default-denied")
    @rpbac.role_required(Role("Admin"))
    def default_denied():
        return "ok"

    response = client.get("/default-denied")

    assert response.status_code == 403
    assert response.get_json()["error"] == "forbidden"
    assert "Missing role" in response.get_json()["message"]


def test_raise_generic_error_propagates_denied_route_error(app, client):
    rpbac = RPBAC(app, raise_generic_error=True)

    @rpbac.role_loader
    def role_loader():
        return []

    @app.route("/generic-denied")
    @rpbac.role_required(Role("Admin"))
    def generic_denied():
        return "ok"

    with pytest.raises(RPBACRoleError):
        client.get("/generic-denied")


def test_constructor_rejection_hook_handles_denied_route(app, client):
    handled_errors = []

    def rejection_hook(error):
        handled_errors.append(error)
        return {"source": "constructor", "message": str(error)}, 418

    rpbac = RPBAC(app, rejection_hook=rejection_hook)

    @rpbac.role_loader
    def role_loader():
        return []

    @app.route("/constructor-hook")
    @rpbac.role_required(Role("Admin"))
    def constructor_hook():
        return "ok"

    response = client.get("/constructor-hook")

    assert response.status_code == 418
    assert response.get_json()["source"] == "constructor"
    assert isinstance(handled_errors[0], RPBACRoleError)


def test_decorator_rejection_hook_handles_route_and_overwrites_constructor_hook(
    app, client
):
    handled_errors = []

    def constructor_hook(error):
        handled_errors.append("constructor")
        return {"source": "constructor"}, 418

    rpbac = RPBAC(app, rejection_hook=constructor_hook)

    @rpbac.role_loader
    def role_loader():
        return []

    with pytest.warns(UserWarning, match="Overwriting"):

        @rpbac.rejection_hook
        def decorator_hook(error):
            handled_errors.append("decorator")
            return {"source": "decorator"}, 419

    @app.route("/decorator-hook")
    @rpbac.role_required(Role("Admin"))
    def decorator_hook_route():
        return "ok"

    response = client.get("/decorator-hook")

    assert response.status_code == 419
    assert response.get_json()["source"] == "decorator"
    assert handled_errors == ["decorator"]


def test_can_method_uses_rpbac_logic_without_templates(app):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def role_loader():
        return ["Editor"]

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read"]

    with app.app_context():
        assert rpbac.can(Role("Admin")) is False
        assert rpbac.can(Permission("post:delete")) is False
        assert rpbac.can(Any(Role("Admin"), Permission("post:read"))) is True
        assert rpbac.can(All(Role("Editor"), Permission("post:read"))) is True


def test_nested_all_any_logic_for_roles_and_permissions(app):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def role_loader():
        return ["Admin", "Editor"]

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read", "post:write"]

    with app.app_context():
        assert rpbac.can(All(Role("Admin"), Permission("post:read"))) is True
        assert rpbac.can(Any(Role("Reader"), Permission("post:write"))) is True
        assert (
            rpbac.can(
                Any(
                    Role("Reader"),
                    All(Role("Admin", "Editor", match="all"), Permission("post:write")),
                )
            )
            is True
        )
        assert rpbac.can(All(Role("Admin"), Permission("post:delete"))) is False
        assert rpbac.can(Any(Role("Reader"), Permission("post:delete"))) is False


def test_user_data_loader_takes_priority_over_role_and_permission_loaders(app, client):
    rpbac = RPBAC(app)

    @rpbac.user_data_loader
    def user_data_loader():
        return {"roles": ["Admin"], "permissions": ["post:read", "post:write"]}

    @app.route("/user-data")
    @rpbac.role_required(Role("Admin"))
    @rpbac.permission_required(Permission("post:write"))
    def user_data_route():
        return "allowed"

    with app.app_context():
        assert rpbac.can(Role("Admin")) is True
        assert rpbac.can(Permission("post:write")) is True

    assert client.get("/user-data").status_code == 200


def test_missing_loaders_raise_runtime_error_when_route_is_protected(app, client):
    rpbac = RPBAC(app)

    @app.route("/needs-role")
    @rpbac.role_required(Role("Admin"))
    def needs_role():
        return "ok"

    @app.route("/needs-perm")
    @rpbac.permission_required(Permission("post:read"))
    def needs_perm():
        return "ok"

    with pytest.raises(RuntimeError, match="No role_loader configured"):
        client.get("/needs-role")

    with pytest.raises(RuntimeError, match="No permission_loader configured"):
        client.get("/needs-perm")


def test_combined_requirements_and_match_modes_work_in_real_routes(app, client):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def role_loader():
        return ["Admin", "Editor"]

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read", "post:write"]

    @app.route("/all-match")
    @rpbac.required(
        All(
            Role("Admin", "Editor", match="all"),
            Permission("post:read", "post:write", match="all"),
        )
    )
    def all_match():
        return "ok"

    @app.route("/any-match")
    @rpbac.required(
        Any(Role("Reader"), Permission("post:delete", "post:read", match="any"))
    )
    def any_match():
        return "ok"

    assert client.get("/all-match").status_code == 200
    assert client.get("/any-match").status_code == 200


def test_empty_role_or_permission_sets_fail_gracefully(app, client):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def role_loader():
        return []

    @rpbac.permission_loader
    def permission_loader():
        return []

    @app.route("/empty-role")
    @rpbac.role_required(Role("Admin"))
    def empty_role():
        return "ok"

    @app.route("/empty-perm")
    @rpbac.permission_required(Permission("post:read"))
    def empty_perm():
        return "ok"

    assert client.get("/empty-role").status_code == 403
    assert client.get("/empty-perm").status_code == 403
