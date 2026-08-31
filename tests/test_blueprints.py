import pytest
from flask import Blueprint, Flask

from src.flask_rpbac import Any, Permission, RPBAC, Role
from src.flask_rpbac.exc import RPBACError


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

    with app.test_request_context("/denied"):
        with pytest.raises(RPBACError):
            denied_route()


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
