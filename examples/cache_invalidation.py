"""Redis-backed authorization caching and post-commit cache invalidation.

Run from the repository root after installing the example dependencies and
starting Redis. Set REDIS_URL for a non-local Redis service. This example uses
the shared SQLAlchemy models and JWT setup in examples/setup/.
"""

from __future__ import annotations

import os

import sqlalchemy as sql
from flask import Flask, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from setup import (
    Permission as DbPermission,
)
from setup import (
    Role as DbRole,
)
from setup import (
    User,
    create_db_data,
    db,
    jwt,
    rpbac,
)

from flask_rpbac import Permission, Role

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "development-only-secret")
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "development-only-jwt-secret"
)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cache_invalidation.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
jwt.init_app(app)
rpbac.init_app(
    app,
    cache_config={
        "type": "redis",
        "url": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        "ttl": 300,
    },
)


@rpbac.load_user_identity
def load_user_identity() -> str:
    return str(get_jwt_identity())


@rpbac.role_loader
def load_roles() -> list[str]:
    user = db.session.get(User, get_jwt_identity())
    return user.get_roles() if user is not None else []


@rpbac.permission_loader
def load_permissions() -> list[str]:
    user = db.session.get(User, get_jwt_identity())
    return user.get_permissions() if user is not None else []


@app.get("/posts")
@jwt_required()
@rpbac.required(Role("Admin") | Permission("post:read"))
def list_posts():
    return jsonify({"message": "Authorized; roles and permissions may be cached."})


@app.patch("/admin/users/<int:user_id>/roles")
@jwt_required()
@rpbac.role_required(Role("Admin"))
def update_user_roles(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "user_not_found"}), 404

    role_names = request.get_json().get("roles", [])
    roles = db.session.scalars(
        sql.select(DbRole).where(DbRole.name.in_(role_names))
    ).all()
    identity = str(user.id)

    user.roles = roles
    db.session.commit()
    rpbac.invalidate_cache(identity)

    return jsonify({"status": "updated", "user_id": user_id})


@app.patch("/admin/roles/<int:role_id>/permissions")
@jwt_required()
@rpbac.role_required(Role("Admin"))
def update_role_permissions(role_id: int):
    role = db.session.get(DbRole, role_id)
    if role is None:
        return jsonify({"error": "role_not_found"}), 404

    identities = {str(user.id) for user in role.users}
    permission_names = request.get_json().get("permissions", [])
    role.permissions = db.session.scalars(
        sql.select(DbPermission).where(DbPermission.name.in_(permission_names))
    ).all()

    db.session.commit()
    for identity in identities:
        rpbac.invalidate_cache(identity)

    return jsonify({"status": "updated", "role_id": role_id})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_db_data()

    app.run(debug=True)
