import sqlalchemy as sql
from flask import Flask, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from setup import Perm, Rolee, User, create_db_data, db, jwt, rpbac

from flask_rpbac import All, Any, Not, Permission, Role

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


# This route requires admin status OR editor + edit permission.
@app.get("/publish")
@jwt_required()
@rpbac.required(
    Any(
        Role(Rolee.ADMIN),
        All(Role(Rolee.EDITOR), Permission(Perm.POST_EDIT)),
    )
)
def publish():
    return jsonify({"message": "Publishing allowed"})


# This route blocks readers from the feature by negating the reader role.
@app.get("/internal")
@jwt_required()
@rpbac.required(Not(Role(Rolee.READER)))
def internal():
    return jsonify({"message": "Internal area"})


# This route allows either the admin role or the read permission.
@app.get("/shared")
@jwt_required()
@rpbac.required(Any(Role(Rolee.ADMIN), Permission(Perm.POST_READ)))
def shared():
    return jsonify({"message": "Shared access"})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_db_data()

    app.run(debug=True)
