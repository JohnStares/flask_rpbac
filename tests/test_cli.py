import json

from click.testing import CliRunner
from flask import Blueprint, Flask

from src.flask_rpbac import RPBAC, Permission, Role


def invoke_audit(app, *args):
    runner = CliRunner()
    with app.app_context():
        return runner.invoke(app.cli, ["rpbac-audit", *args])


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


def test_audit_defaults_to_protected_routes_and_skips_static_and_missing_views():
    app = Flask(__name__)
    rpbac = RPBAC(app)

    @app.get("/open")
    def open_route():
        return "open"

    @app.get("/secured")
    @rpbac.role_required(Role("admin"))
    def secured_route():
        return "secured"

    app.add_url_rule("/missing", endpoint="missing_view")

    result = invoke_audit(app)

    assert result.exit_code == 0
    assert "/secured" in result.output
    assert "/open" not in result.output
    assert "/missing" not in result.output
    assert "/static/" not in result.output


def test_audit_unprotected_flag_lists_only_unprotected_routes():
    app = Flask(__name__)
    rpbac = RPBAC(app)

    @app.get("/open-one")
    def open_one():
        return "open"

    @app.get("/secured-one")
    @rpbac.role_required(Role("admin"))
    def secured_one():
        return "secured"

    result = invoke_audit(app, "-u")

    assert result.exit_code == 0
    assert "/open-one" in result.output
    assert "/secured-one" not in result.output


def test_audit_all_verbose_lists_protected_and_unprotected_routes():
    app = Flask(__name__)
    rpbac = RPBAC(app)

    @app.get("/open-all")
    def open_all():
        return "open"

    @app.route("/secured-all", methods=["GET", "POST"])
    @rpbac.required(Role("admin") & Permission("report:view"))
    def secured_all():
        return "secured"

    result = invoke_audit(app, "-a", "-v")

    assert result.exit_code == 0
    assert "/open-all" in result.output
    assert "/secured-all" in result.output
    assert "GET" in result.output
    assert "POST" in result.output
    assert "Role" in result.output
    assert "Permission" in result.output


def test_audit_json_reports_protected_route_and_summary():
    app = Flask(__name__)
    rpbac = RPBAC(app)

    @app.get("/open-json")
    def open_json():
        return "open"

    @app.get("/secured-json")
    @rpbac.required(Role("admin") & Permission("post:read"))
    def secured_json():
        return "secured"

    result = invoke_audit(app, "--json")

    assert result.exit_code == 0
    report = json.loads(result.output)
    assert report["summary"] == {
        "routes_scanned": 1,
        "protected": 1,
        "unprotected": 0,
    }
    assert report["findings"] == [
        {
            "rule": "/secured-json",
            "bp_name": None,
            "bp_req": "None",
            "route_req": "All(Role('admin', match=any), Permission('post:read', match=all))",
        }
    ]


def test_audit_json_unprotected_and_all_modes_report_correct_counts():
    app = Flask(__name__)
    rpbac = RPBAC(app)

    @app.get("/open-json-modes")
    def open_json_modes():
        return "open"

    @app.get("/secured-json-modes")
    @rpbac.role_required(Role("staff"))
    def secured_json_modes():
        return "secured"

    unprotected_result = invoke_audit(app, "-u", "--json", "--verbose")
    assert unprotected_result.exit_code == 0
    unprotected_report = json.loads(unprotected_result.output)
    assert unprotected_report["summary"] == {
        "routes_scanned": 1,
        "protected": 0,
        "unprotected": 1,
    }
    assert len(unprotected_report["findings"]) == 1
    unprotected_finding = unprotected_report["findings"][0]
    assert unprotected_finding["rule"] == "/open-json-modes"
    assert set(unprotected_finding["methods"]) == {"GET", "HEAD", "OPTIONS"}
    assert unprotected_finding["view"] == "open_json_modes"

    all_result = invoke_audit(app, "-a", "--json", "--verbose")
    assert all_result.exit_code == 0
    all_report = json.loads(all_result.output)
    assert all_report["summary"] == {
        "routes_scanned": 2,
        "protected": 1,
        "unprotected": 1,
    }
    assert {item["rule"] for item in all_report["findings"]} == {
        "/open-json-modes",
        "/secured-json-modes",
    }

    compact_unprotected_result = invoke_audit(app, "-u", "--json")
    assert compact_unprotected_result.exit_code == 0
    compact_unprotected_report = json.loads(compact_unprotected_result.output)
    assert compact_unprotected_report["summary"] == {
        "routes_scanned": 1,
        "protected": 0,
        "unprotected": 1,
    }
    assert compact_unprotected_report["findings"] == [{"rule": "/open-json-modes"}]


def test_audit_json_includes_blueprint_and_route_requirements():
    app = Flask(__name__)
    rpbac = RPBAC(app)
    admin = Blueprint("admin", __name__)
    rpbac.protect_blueprint(admin, Role("staff"))

    @admin.get("/reports")
    @rpbac.permission_required(Permission("report:view"))
    def reports():
        return "reports"

    app.register_blueprint(admin, url_prefix="/admin")
    result = invoke_audit(app, "--json", "--verbose")

    assert result.exit_code == 0
    report = json.loads(result.output)
    assert report["summary"] == {
        "routes_scanned": 1,
        "protected": 1,
        "unprotected": 0,
    }
    finding = report["findings"][0]
    assert finding["rule"] == "/admin/reports"
    assert finding["bp_name"] == "admin"
    assert finding["bp_req"] == "Role('staff', match=any)"
    assert finding["route_req"] == "Permission('report:view', match=all)"
    assert finding["view"] == "admin.reports"
    assert "GET" in finding["methods"]


def test_audit_text_shows_blueprint_and_route_requirements_without_verbose():
    app = Flask(__name__)
    rpbac = RPBAC(app)
    admin = Blueprint("text_admin", __name__)
    rpbac.protect_blueprint(admin, Role("staff"))

    @admin.get("/reports")
    @rpbac.permission_required(Permission("report:view"))
    def reports():
        return "reports"

    app.register_blueprint(admin, url_prefix="/text-admin")
    result = invoke_audit(app)

    assert result.exit_code == 0
    assert "text_admin" in result.output
    assert "/text-admin/reports" in result.output
    assert "Role('staff', match=any)" in result.output
    assert "Permission('report:view', match=all)" in result.output


def test_audit_all_unprotected_flag_prefers_unprotected_only_mode():
    app = Flask(__name__)
    RPBAC(app)

    @app.get("/open-flags")
    def open_flags():
        return "open"

    result = invoke_audit(app, "-u", "-a")

    assert result.exit_code == 0
    assert "/open-flags" in result.output


def test_audit_emits_nothing_when_default_mode_has_no_protected_routes():
    app = Flask(__name__)
    RPBAC(app)

    @app.get("/only-open")
    def only_open():
        return "open"

    result = invoke_audit(app)

    assert result.exit_code == 0
    assert result.output == ""
