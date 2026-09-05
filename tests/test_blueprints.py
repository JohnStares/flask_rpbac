import pytest
from flask import Blueprint, Flask

from src.flask_rpbac import RPBAC, Any, Permission, Role
from src.flask_rpbac.exc import RPBACError, RPBACRoleError


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_blueprint_protects_allowed_routes_and_uses_403_for_denials(app, client):
    rpbac = RPBAC(app)
    bp = Blueprint("admin_bp", __name__)

    @rpbac.role_loader
    def role_loader():
        return ["Admin"]

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read"]

    rpbac.protect_blueprint(bp, Role("Admin"))

    @bp.route("/admin")
    @rpbac.permission_required(Permission("post:read"))
    def admin_route():
        return "ok"

    app.register_blueprint(bp)

    assert client.get("/admin").status_code == 200

    @rpbac.role_loader
    def role_loader_restricted():
        return ["Editor"]

    assert client.get("/admin").status_code == 403


def test_blueprint_any_requirement_allows_access_when_any_branch_matches(app, client):
    rpbac = RPBAC(app)
    bp = Blueprint("staff_bp", __name__)

    @rpbac.role_loader
    def role_loader():
        return ["Reader"]

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read"]

    rpbac.protect_blueprint(bp, Any(Role("Admin"), Permission("post:read")))

    @bp.route("/staff")
    def staff_route():
        return "allowed"

    app.register_blueprint(bp)

    response = client.get("/staff")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "allowed"


def test_blueprint_denied_access_raises_rpbac_error_in_request_context(app):
    rpbac = RPBAC(app)
    bp = Blueprint("denied_bp", __name__)

    @rpbac.role_loader
    def role_loader():
        return ["Editor"]

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read"]

    rpbac.protect_blueprint(bp, Role("Admin"))

    @bp.route("/denied")
    @rpbac.required(Permission("post:delete"))
    def denied_route():
        return "blocked"

    app.register_blueprint(bp)

    with app.test_request_context("/denied"), pytest.raises(RPBACError):
        denied_route()


def test_default_rpbac_error_handler_returns_json_for_denied_blueprint_route(
    app, client
):
    rpbac = RPBAC(app)
    bp = Blueprint("default_error_bp", __name__)

    @rpbac.role_loader
    def role_loader():
        return []

    rpbac.protect_blueprint(bp, Role("Admin"))

    @bp.route("/default-blueprint-denied")
    def default_blueprint_denied():
        return "ok"

    app.register_blueprint(bp)
    response = client.get("/default-blueprint-denied")

    assert response.status_code == 403
    assert response.get_json()["error"] == "forbidden"
    assert "Missing role" in response.get_json()["message"]


def test_raise_generic_error_propagates_denied_blueprint_route(app, client):
    rpbac = RPBAC(app, raise_generic_error=True)
    bp = Blueprint("generic_error_bp", __name__)

    @rpbac.role_loader
    def role_loader():
        return []

    rpbac.protect_blueprint(bp, Role("Admin"))

    @bp.route("/generic-blueprint-denied")
    def generic_blueprint_denied():
        return "ok"

    app.register_blueprint(bp)

    with pytest.raises(RPBACRoleError):
        client.get("/generic-blueprint-denied")


def test_constructor_rejection_hook_handles_denied_blueprint_route(app, client):
    handled_errors = []

    def rejection_hook(error):
        handled_errors.append(error)
        return {"source": "constructor", "message": str(error)}, 418

    rpbac = RPBAC(app, rejection_hook=rejection_hook)
    bp = Blueprint("constructor_hook_bp", __name__)

    @rpbac.role_loader
    def role_loader():
        return []

    rpbac.protect_blueprint(bp, Role("Admin"))

    @bp.route("/constructor-blueprint-hook")
    def constructor_blueprint_hook():
        return "ok"

    app.register_blueprint(bp)
    response = client.get("/constructor-blueprint-hook")

    assert response.status_code == 418
    assert response.get_json()["source"] == "constructor"
    assert isinstance(handled_errors[0], RPBACRoleError)


def test_decorator_rejection_hook_handles_blueprint_and_overwrites_constructor_hook(
    app, client
):
    handled_errors = []

    def constructor_hook(error):
        handled_errors.append("constructor")
        return {"source": "constructor"}, 418

    rpbac = RPBAC(app, rejection_hook=constructor_hook)
    bp = Blueprint("decorator_hook_bp", __name__)

    @rpbac.role_loader
    def role_loader():
        return []

    with pytest.warns(UserWarning, match="Overwriting"):

        @rpbac.rejection_hook
        def decorator_hook(error):
            handled_errors.append("decorator")
            return {"source": "decorator"}, 419

    rpbac.protect_blueprint(bp, Role("Admin"))

    @bp.route("/decorator-blueprint-hook")
    def decorator_blueprint_hook():
        return "ok"

    app.register_blueprint(bp)
    response = client.get("/decorator-blueprint-hook")

    assert response.status_code == 419
    assert response.get_json()["source"] == "decorator"
    assert handled_errors == ["decorator"]


def test_blueprint_missing_role_loader_raises_runtime_error(app, client):
    rpbac = RPBAC(app)
    bp = Blueprint("admin_bp", __name__)

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read"]

    rpbac.protect_blueprint(bp, Role("Admin"))

    @bp.route("/admin")
    def admin_route():
        return "ok"

    app.register_blueprint(bp)

    with pytest.raises(RuntimeError, match="No role_loader configured"):
        client.get("/admin")


def test_blueprint_without_app_initialization_raises_assertion_error():
    rpbac = RPBAC()
    bp = Blueprint("admin_bp", __name__)
    rpbac.protect_blueprint(bp, Role("Admin"))

    @bp.route("/admin")
    def admin_route():
        return "ok"

    with pytest.raises(
        AssertionError, match="Please initialize your application into flask RPBAC"
    ):
        admin_route()


def test_blueprint_and_route_requirements_are_combined(app, client):
    rpbac = RPBAC(app)
    bp = Blueprint("ops_bp", __name__)

    @rpbac.role_loader
    def role_loader():
        return ["Admin"]

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read"]

    rpbac.protect_blueprint(bp, Role("Admin"))

    @bp.route("/ops")
    @rpbac.permission_required(Permission("post:read"))
    def ops_route():
        return "ops"

    app.register_blueprint(bp)

    assert client.get("/ops").status_code == 200

    @rpbac.role_loader
    def role_loader_restricted():
        return ["Editor"]

    assert client.get("/ops").status_code == 403
