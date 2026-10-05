import pytest
from flask import Blueprint, Flask

from src.flask_rpbac import RPBAC, All, Any, Permission, Predicate, Role
from src.flask_rpbac.exc import RPBACPredicateError


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_predicate_receives_route_kwargs_roles_and_permissions(app, client):
    rpbac = RPBAC(app)
    checks = []

    @rpbac.role_loader
    def load_roles():
        return ["editor"]

    @rpbac.permission_loader
    def load_permissions():
        return ["post:write"]

    def can_edit(ctx):
        checks.append(ctx)
        return (
            ctx.kwargs == {"post_id": 42}
            and set(ctx.roles) == {"editor"}
            and set(ctx.permissions) == {"post:write"}
        )

    @app.route("/posts/<int:post_id>")
    @rpbac.required(Predicate(can_edit))
    def edit_post(post_id):
        return str(post_id)

    response = client.get("/posts/42")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "42"
    assert len(checks) == 1


def test_predicate_can_authorize_without_role_or_permission_loaders(app, client):
    rpbac = RPBAC(app)

    @app.route("/documents/<int:document_id>")
    @rpbac.required(Predicate(lambda ctx: ctx.kwargs["document_id"] == 7))
    def document(document_id):
        return "allowed"

    assert client.get("/documents/7").status_code == 200
    assert client.get("/documents/8").status_code == 403


def test_failed_predicate_returns_default_forbidden_response(app, client):
    rpbac = RPBAC(app)

    @app.route("/documents/<int:document_id>")
    @rpbac.required(Predicate(lambda ctx: False))
    def denied_document(document_id):
        return "must not run"

    response = client.get("/documents/7")

    assert response.status_code == 403
    assert response.get_json()["error"] == "forbidden"
    assert "Authz Failed" in response.get_json()["message"]


def test_failed_predicate_raises_structured_error_when_generic_errors_enabled(
    app, client
):
    rpbac = RPBAC(app, raise_generic_error=True)
    predicate = Predicate(lambda ctx: False)

    @app.route("/documents/<int:document_id>")
    @rpbac.required(predicate)
    def denied_document(document_id):
        return "must not run"

    with pytest.raises(RPBACPredicateError) as raised:
        client.get("/documents/7")

    assert raised.value.func is predicate.func
    assert raised.value.ctx.kwargs == {"document_id": 7}


def test_predicate_is_not_called_when_an_earlier_all_requirement_fails(app, client):
    rpbac = RPBAC(app)
    called = False

    @rpbac.role_loader
    def load_roles():
        return []

    def should_not_run(ctx):
        nonlocal called
        called = True
        return True

    @app.route("/documents/<int:document_id>")
    @rpbac.required(All(Role("admin"), Predicate(should_not_run)))
    def denied_document(document_id):
        return "must not run"

    assert client.get("/documents/7").status_code == 403
    assert called is False


def test_predicate_is_not_called_when_an_admin_branch_matches(app, client):
    rpbac = RPBAC(app)
    called = False

    @rpbac.role_loader
    def load_roles():
        return ["admin"]

    def should_not_run(ctx):
        nonlocal called
        called = True
        return False

    @app.route("/documents/<int:document_id>")
    @rpbac.required(Any(Role("admin"), Predicate(should_not_run)))
    def edit_document(document_id):
        return "allowed"

    assert client.get("/documents/7").status_code == 200
    assert called is False


def test_predicate_composes_with_permission_and_can_allow_or_deny_objects(app, client):
    rpbac = RPBAC(app)
    current_user = {"id": 10}

    @rpbac.permission_loader
    def load_permissions():
        return ["post:write"]

    def owns_post(ctx):
        return int(ctx.kwargs["post_id"]) == current_user["id"]

    @app.route("/posts/<int:post_id>")
    @rpbac.required(All(Permission("post:write"), Predicate(owns_post)))
    def edit_post(post_id):
        return "updated"

    assert client.get("/posts/10").status_code == 200
    assert client.get("/posts/11").status_code == 403


def test_predicate_can_read_context_from_user_data_loader(app, client):
    rpbac = RPBAC(app)

    @rpbac.user_data_loader
    def load_user_data():
        return {"roles": ["editor"], "permissions": ["post:write"]}

    @app.route("/posts/<int:post_id>")
    @rpbac.required(
        Predicate(
            lambda ctx: (
                "editor" in ctx.roles
                and "post:write" in ctx.permissions
                and ctx.kwargs["post_id"] == 3
            )
        )
    )
    def edit_post(post_id):
        return "updated"

    assert client.get("/posts/3").status_code == 200


def test_identifier_from_kwargs_uses_route_identifier_as_loaded_role(app, client):
    rpbac = RPBAC(app)
    current_user = {"roles": ["user-1"]}

    @rpbac.role_loader
    def load_roles():
        return current_user["roles"]

    @app.route("/users/<user_id>")
    @rpbac.required(Role.identifier_from_kwargs("user_id"))
    def user_profile(user_id):
        return user_id

    assert client.get("/users/user-1").status_code == 200
    assert client.get("/users/user-2").status_code == 403


def test_predicate_missing_route_key_propagates_key_error(app, client):
    rpbac = RPBAC(app, raise_generic_error=True)

    @app.route("/documents/<int:document_id>")
    @rpbac.required(Predicate(lambda ctx: ctx.kwargs["other_id"] == 1))
    def document(document_id):
        return "must not run"

    with pytest.raises(KeyError, match="other_id"):
        client.get("/documents/1")


def test_predicate_exception_propagates_unchanged(app, client):
    rpbac = RPBAC(app, raise_generic_error=True)

    def broken_predicate(ctx):
        raise ValueError("database unavailable")

    @app.route("/documents/<int:document_id>")
    @rpbac.required(Predicate(broken_predicate))
    def document(document_id):
        return "must not run"

    with pytest.raises(ValueError, match="database unavailable"):
        client.get("/documents/1")


def test_predicate_works_on_blueprint_routes_with_route_kwargs(app, client):
    rpbac = RPBAC(app)
    documents = Blueprint("documents", __name__, url_prefix="/documents")
    seen = []

    def can_read(ctx):
        seen.append(ctx.kwargs["document_id"])
        return ctx.kwargs["document_id"] == 5

    @documents.route("/<int:document_id>")
    @rpbac.required(Predicate(can_read))
    def document(document_id):
        return "allowed"

    app.register_blueprint(documents)

    assert client.get("/documents/5").status_code == 200
    assert client.get("/documents/6").status_code == 403
    assert seen == [5, 6]


def test_cached_user_data_keeps_predicate_kwargs_request_specific(app, client):
    rpbac = RPBAC(app, cache_config={"type": "memory"})
    calls = {"identity": 0, "user_data": 0}

    @rpbac.load_user_identity
    def load_identity():
        calls["identity"] += 1
        return "user-1"

    @rpbac.user_data_loader
    def load_user_data():
        calls["user_data"] += 1
        return {"roles": ["editor"], "permissions": ["post:write"]}

    @app.route("/posts/<int:post_id>")
    @rpbac.required(Predicate(lambda ctx: ctx.kwargs["post_id"] == 2))
    def edit_post(post_id):
        return "updated"

    assert client.get("/posts/2").status_code == 200
    assert client.get("/posts/1").status_code == 403
    assert calls == {"identity": 2, "user_data": 1}


def test_all_predicates_share_query_result_through_request_pstore(app, client):
    rpbac = RPBAC(app)
    query_calls = []

    def load_record(ctx):
        record_id = ctx.kwargs["record_id"]
        query_calls.append(record_id)
        ctx.pstore["record"] = {"id": record_id, "owner_id": 73}
        return True

    def verify_record_owner(ctx):
        record = ctx.pstore["record"]
        return record["id"] == ctx.kwargs["record_id"] and record["owner_id"] == 73

    @app.get("/shared-all/<int:record_id>")
    @rpbac.required(All(Predicate(load_record), Predicate(verify_record_owner)))
    def shared_all(record_id):
        return "allowed"

    response = client.get("/shared-all/18")

    assert response.status_code == 200
    assert query_calls == [18]


def test_any_predicates_share_stored_result_when_first_branch_denies(app, client):
    rpbac = RPBAC(app)
    query_calls = []

    def load_record_for_fallback(ctx):
        record_id = ctx.kwargs["record_id"]
        query_calls.append(record_id)
        ctx.pstore["record"] = {"id": record_id, "published": True}
        # Deny this branch so Any evaluates the next predicate, using the query result.
        return False

    def is_published(ctx):
        return ctx.pstore["record"]["published"]

    @app.get("/shared-any/<int:record_id>")
    @rpbac.required(Any(Predicate(load_record_for_fallback), Predicate(is_published)))
    def shared_any(record_id):
        return "published"

    response = client.get("/shared-any/29")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "published"
    assert query_calls == [29]


@pytest.mark.parametrize("combinator", [All, Any])
def test_predicate_reading_pstore_before_producer_raises_key_error(
    app, client, combinator
):
    rpbac = RPBAC(app, raise_generic_error=True)

    def consume_before_load(ctx):
        return ctx.pstore["record"]["authorized"]

    def load_record(ctx):
        ctx.pstore["record"] = {"authorized": True}
        return True

    @app.get("/pstore-order/<int:record_id>")
    @rpbac.required(combinator(Predicate(consume_before_load), Predicate(load_record)))
    def pstore_order(record_id):
        return "unreachable for this ordering"

    with pytest.raises(KeyError, match="record"):
        client.get("/pstore-order/3")


def test_pstore_is_fresh_for_each_request(app, client):
    rpbac = RPBAC(app)
    observed_values = []

    def store_request_value(ctx):
        value = ctx.kwargs["value"]
        ctx.pstore["value"] = value
        observed_values.append(value)
        return True

    def verify_request_value(ctx):
        return ctx.pstore["value"] == ctx.kwargs["value"]

    @app.get("/pstore-isolation/<value>")
    @rpbac.required(
        All(Predicate(store_request_value), Predicate(verify_request_value))
    )
    def pstore_isolation(value):
        return value

    assert client.get("/pstore-isolation/first").get_data(as_text=True) == "first"
    assert client.get("/pstore-isolation/second").get_data(as_text=True) == "second"
    assert observed_values == ["first", "second"]
