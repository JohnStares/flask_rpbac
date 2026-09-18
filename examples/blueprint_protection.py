import sqlalchemy as sql
from flask import Blueprint, Flask, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from setup import Perm, Post, Rolee, User, create_db_data, db, jwt, rpbac

from flask_rpbac import Any, Permission, Role

app = Flask(__name__)

app.config["SECRET_KEY"] = "something-super-super-super-secret"  # Change this!
app.config["JWT_SECRET_KEY"] = (
    "something-super-super-super-super-secret"  # Change this!
)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
jwt.init_app(app)
rpbac.init_app(app)


@rpbac.role_loader
def get_user_roles():
    user = db.session.get(User, get_jwt_identity())
    return user.get_roles() if user is not None else []


@rpbac.permission_loader
def get_user_permissions():
    user = db.session.get(User, get_jwt_identity())
    return user.get_permissions() if user is not None else []


@app.post("/login")
def login():
    data = request.get_json()
    email = data.get("email", "")
    password = data.get("password", "")

    user = db.session.scalar(sql.select(User).where(User.email == email))

    if user is not None and user.compare_hashed_password(password):
        token = create_access_token(identity=user)
        return jsonify({"token": token}), 200

    return jsonify({"msg": "Invalid username or password"}), 401


admin_bp = Blueprint("admin_bp", __name__)

# Protect the whole blueprint. Any admin or user with the delete permission can access
# every route in this blueprint, while route-level checks can add more rules.
rpbac.protect_blueprint(admin_bp, Any(Role(Rolee.ADMIN), Permission(Perm.POST_DELETE)))


@admin_bp.get("/reports")
def reports():
    return jsonify({"message": "Admin reports available"})


@admin_bp.get("/audit")
@jwt_required()
def audit():
    return jsonify({"message": "Audit log access granted"})


app.register_blueprint(admin_bp)


@app.get("/posts")
@jwt_required()
@rpbac.role_required(Role(Rolee.ADMIN, Rolee.EDITOR, Rolee.READER))
def get_posts():
    posts = db.session.execute(sql.select(Post.id, Post.title, Post.content)).all()
    return jsonify(
        [
            {"id": post.id, "title": post.title, "content": post.content}
            for post in posts
        ]
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_db_data()

    app.run(debug=True)
