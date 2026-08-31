import io

from click.testing import CliRunner
from flask import Flask

from src.flask_rpbac import Permission, RPBAC, Role


def test_rpbac_route_requirements_cli_lists_protected_routes():
    app = Flask(__name__)
    app.config["TESTING"] = True
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def role_loader():
        return ["Admin"]

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read"]

    @app.route("/admin")
    @rpbac.role_required(Role("Admin"))
    def admin_route():
        return "ok"

    @app.route("/editor")
    @rpbac.required(Permission("post:read"))
    def editor_route():
        return "ok"

    runner = CliRunner()
    with app.app_context():
        result = runner.invoke(app.cli, ["rpbac-audit"])

    assert result.exit_code == 0
    output = result.output
    assert "/admin" in output or "admin" in output.lower()
    assert "/editor" in output or "editor" in output.lower()


def test_rpbac_route_requirements_cli_verbose_output_contains_details():
    app = Flask(__name__)
    app.config["TESTING"] = True
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def role_loader():
        return ["Admin"]

    @rpbac.permission_loader
    def permission_loader():
        return ["post:read"]

    @app.route("/audit")
    @rpbac.required(Role("Admin") & Permission("post:read"))
    def audit_route():
        return "ok"

    runner = CliRunner()
    with app.app_context():
        result = runner.invoke(app.cli, ["rpbac-audit", "--verbose"])

    assert result.exit_code == 0
    assert "audit" in result.output.lower()
    assert "Role" in result.output or "Permission" in result.output
