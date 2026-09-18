import sqlalchemy as sql
from flask import Flask, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from setup import Post, Rolee, User, create_db_data, db, jwt, rpbac

from flask_rpbac import Role

app = Flask(__name__)

app.config["SECRET_KEY"] = "something-super-super-super-secret"  # Change this!
app.config["JWT_SECRET_KEY"] = "something-super-super-super-secret"  # Change this!
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
jwt.init_app(app)
rpbac.init_app(app)


# Register rpbac loaders
# This way, rpbac knows how to get the current user roles and
# permissions
@rpbac.role_loader
def get_user_roles():
    user = db.session.get(User, get_jwt_identity())

    return user.get_roles() if user is not None else []


@rpbac.permission_loader
def get_user_permissions():
    user = db.session.get(User, get_jwt_identity())

    return user.get_permissions() if user is not None else []


# routes
@app.post("/login")
def login():
    data = request.get_json()

    # Check the setup/__init__.py for create_users function
    # The already pre defined email and passwords are there
    email = data.get("email", "")
    password = data.get("password", "")

    user = db.session.scalar(sql.select(User).where(User.email == email))

    if user is not None and user.compare_hashed_password(password):
        token = create_access_token(identity=user)

        return jsonify({"token": token}), 200

    return jsonify({"msg": "Invalid username or password"}), 401


# Only users with any of the roles can access this route.
@app.get("/posts")
@jwt_required()
@rpbac.role_required(Role(Rolee.ADMIN, Rolee.EDITOR, Rolee.READER))
def get_posts():
    posts = db.session.execute(sql.select(Post.id, Post.title, Post.content)).all()

    _posts = [
        {"id": post.id, "title": post.title, "content": post.content} for post in posts
    ]

    return jsonify({"posts": _posts})


# Only users with admin or editor role can make changes to this resource
@app.patch("/post/<id>")
@jwt_required()
@rpbac.role_required(Role(Rolee.ADMIN, Rolee.EDITOR))
def edit_post(id):
    data = request.get_json()

    title = data.get("title")
    content = data.get("content")

    post = db.session.get(Post, id)

    if post is None:
        return jsonify({"msg": "Post not found"}), 404

    if title is not None:
        post.title = title

    if content is not None:
        post.content = content

    if title is not None or content is not None:
        db.session.commit()

    return jsonify({"msg": "Post modified"}), 200


# Only users with admin role can delete a post
@app.delete("/post/<id>")
@jwt_required()
@rpbac.role_required(Role(Rolee.ADMIN))
def delete_post(id):
    post = db.session.get(Post, id)

    if post is None:
        return jsonify({"msg": "Post not found"}), 404

    db.session.delete(post)
    db.session.commit()

    return jsonify({"msg": "Post deleted"}), 200


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        create_db_data()

    app.run(debug=True)
