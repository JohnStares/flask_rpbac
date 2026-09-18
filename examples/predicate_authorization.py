import sqlalchemy as sql
from flask import Flask, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from setup import Perm, Post, Rolee, User, create_db_data, db, jwt, rpbac

from flask_rpbac import All, Any, Permission, Predicate, Role, RPBACBuildContext

app = Flask(__name__)

app.config["SECRET_KEY"] = "something-super-super-super-secret"  # Change this!
app.config["JWT_SECRET_KEY"] = "something-super-super-super-secret"  # Change this!
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


# Predicates let you express authorization based on dynamic context such as route arguments.
def owns_post(ctx: RPBACBuildContext):
    post_id = ctx.kwargs.get("id")

    if post_id is None:
        return False

    post = db.session.get(Post, post_id)
    return bool(post is not None and str(post.user_id) == get_jwt_identity())


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


# Admins can update any post, or editors can update their own post if they also
# have the edit permission.
@app.patch("/post/<id>")
@jwt_required()
@rpbac.required(
    Any(
        Role(Rolee.ADMIN),
        All(Permission(Perm.POST_EDIT), Predicate(owns_post)),
    )
)
def edit_post(id):
    post = db.session.get(Post, id)
    if post is None:
        return jsonify({"msg": "Post not found"}), 404

    data = request.get_json()
    if "title" in data:
        post.title = data["title"]
    if "content" in data:
        post.content = data["content"]

    db.session.commit()
    return jsonify({"msg": "Post modified"}), 200


# Admins can view any post, while regular readers can only view the post they own.
@app.get("/post/<id>")
@jwt_required()
@rpbac.required(
    Any(
        Role(Rolee.ADMIN),
        All(Permission(Perm.POST_READ), Predicate(owns_post)),
    )
)
def get_post(id):
    post = db.session.get(Post, id)
    if post is None:
        return jsonify({"msg": "Post not found"}), 404

    return jsonify({"id": post.id, "title": post.title, "content": post.content})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_db_data()

    app.run(debug=True)
