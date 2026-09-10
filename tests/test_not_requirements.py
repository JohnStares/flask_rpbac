import pytest
from flask import Flask

from src.flask_rpbac import (
    RPBAC,
    All,
    Any,
    Not,
    Permission,
    Predicate,
    Role,
)


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_not_allows_endpoint_when_role_or_permission_is_missing(app, client):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def load_roles():
        return ["editor"]

    @rpbac.permission_loader
    def load_permissions():
        return ["post:read"]

    @app.route("/without-admin")
    @rpbac.required(Not(Role("admin"), Permission("post:delete")))
    def without_admin():
        return "allowed"

    response = client.get("/without-admin")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "allowed"


def test_not_denies_endpoint_when_any_requirement_passes(app, client):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def load_roles():
        return ["editor"]

    @app.route("/without-editor")
    @rpbac.required(Not(Role("editor")))
    def without_editor():
        return "must not run"

    response = client.get("/without-editor")

    assert response.status_code == 403
    assert response.get_json()["error"] == "forbidden"
    assert "Negation Denied" in response.get_json()["message"]


def test_not_checks_all_requirements_before_allowing_endpoint(app, client):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def load_roles():
        return []

    @rpbac.permission_loader
    def load_permissions():
        return []

    @app.route("/without-access")
    @rpbac.required(Not(Role("admin"), Permission("post:delete")))
    def without_access():
        return "allowed"

    response = client.get("/without-access")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "allowed"


def test_not_stops_at_first_passing_requirement(app, client):
    rpbac = RPBAC(app)
    predicate_called = False

    @rpbac.role_loader
    def load_roles():
        return ["editor"]

    def should_not_be_checked(ctx):
        nonlocal predicate_called
        predicate_called = True
        return False

    @app.route("/short-circuit")
    @rpbac.required(Not(Role("editor"), Predicate(should_not_be_checked)))
    def short_circuit():
        return "must not run"

    response = client.get("/short-circuit")

    assert response.status_code == 403
    assert predicate_called is False


def test_not_inverts_predicate_boolean_result(app, client):
    rpbac = RPBAC(app)

    @app.route("/predicate-not-true")
    @rpbac.required(Not(Predicate(lambda ctx: True)))
    def predicate_not_true():
        return "must not run"

    @app.route("/predicate-not-false")
    @rpbac.required(Not(Predicate(lambda ctx: False)))
    def predicate_not_false():
        return "allowed"

    assert client.get("/predicate-not-true").status_code == 403
    response = client.get("/predicate-not-false")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "allowed"


def test_empty_not_allows_endpoint_without_loaders(app, client):
    rpbac = RPBAC(app)

    @app.route("/empty-not")
    @rpbac.required(Not())
    def empty_not():
        return "allowed"

    response = client.get("/empty-not")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "allowed"


def test_not_composes_with_all_and_any_on_endpoints(app, client):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def load_roles():
        return ["editor"]

    @rpbac.permission_loader
    def load_permissions():
        return ["post:read"]

    @app.route("/all-composition")
    @rpbac.required(All(Not(Role("admin")), Permission("post:read")))
    def all_composition():
        return "allowed"

    @app.route("/any-composition")
    @rpbac.required(Any(Not(Role("admin")), Permission("post:delete")))
    def any_composition():
        return "allowed"

    assert client.get("/all-composition").status_code == 200
    assert client.get("/any-composition").status_code == 200


def test_nested_not_inverts_an_endpoint_requirement(app, client):
    rpbac = RPBAC(app)

    @rpbac.role_loader
    def load_roles():
        return ["admin"]

    @app.route("/nested-not")
    @rpbac.required(Not(Not(Role("admin"))))
    def nested_not():
        return "allowed"

    response = client.get("/nested-not")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "allowed"


def test_not_propagates_unexpected_predicate_exceptions(app, client):
    rpbac = RPBAC(app, raise_generic_error=True)

    def broken_predicate(ctx):
        raise ValueError("database unavailable")

    @app.route("/broken-not")
    @rpbac.required(Not(Predicate(broken_predicate)))
    def broken_not():
        return "must not run"

    with pytest.raises(ValueError, match="database unavailable"):
        client.get("/broken-not")
