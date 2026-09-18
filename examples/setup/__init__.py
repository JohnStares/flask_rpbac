import sqlalchemy as sql
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

from flask_rpbac import RPBAC

db = SQLAlchemy()
jwt = JWTManager()
rpbac = RPBAC()


class Perm:
    POST_CREATE = "post:create"
    POST_READ = "post:read"
    POST_EDIT = "post:edit"
    POST_DELETE = "post:delete"


class Rolee:
    ADMIN = "Admin"
    EDITOR = "Editor"
    READER = "Reader"


# Rough functions just to populate the database with data.
# Normally you won't create your users, roles and permissoins
# in this manner.
def create_users():
    """A helper function to help create users"""

    from . import db

    users_name = ["John", "Stares", "Smart"]
    users_email = ["john@gmail.com", "stares@gmail.com", "smart@gmail.com"]

    users_obj = []

    for i in range(len(users_name)):
        user_exist = db.session.scalar(
            sql.select(sql.exists().where(User.email == users_email[i]))
        )

        if not user_exist:
            user_details = {"name": users_name[i], "email": users_email[i]}

            user = User(**user_details)
            db.session.add(user)

            user.hash_password("1234")

            db.session.commit()

            users_obj.append(user)

    return users_obj


def create_roles(users):
    """A helper function to create roles"""

    roles = ["Admin", "Editor", "Reader"]

    _roles = []

    for i in range(len(roles)):
        role_exist = db.session.scalar(
            sql.select(sql.exists().where(Role.name == roles[i]))
        )

        if not role_exist:
            role = Role(name=roles[i])

            db.session.add(role)

            if users is not None:
                role.users.append(users[i])

                db.session.commit()

            _roles.append(role)

    return _roles


def create_permissions(roles):
    """A helper function to create permissions"""

    permissions = ["post:create", "post:edit", "post:read", "post:delete"]

    for i in range(len(permissions)):
        perm_exist = db.session.scalar(
            sql.select(sql.exists().where(Permission.name == permissions[i]))
        )

        if not perm_exist:
            perm = Permission(name=permissions[i])

            db.session.add(perm)

            if roles is not None:
                for role in roles:
                    if role.name == "Admin":
                        perm.roles.append(role)

                    if role.name == "Editor" and (
                        perm.name == "post:edit" or perm.name == "post:read"
                    ):
                        perm.roles.append(role)

                    if role.name == "Reader" and perm.name == "post:read":
                        perm.roles.append(role)

                db.session.commit()


def create_db_data():
    """An ochestrator function"""
    from . import db

    users = create_users()
    roles = create_roles(users)
    create_permissions(roles)

    post_title = ["Title1", "Title2", "Title3", "Title4"]
    post_content = ["Content1", "Content2", "Content3", "Content4"]

    for i in range(len(post_title)):
        post_exists = db.session.scalar(
            sql.select(sql.exists().where(Post.title == post_title[i]))
        )

        if not post_exists and users is not None:
            for user in users:
                if (
                    "Admin" in [r.name for r in user.roles]
                    and post_title[i] in ["Title1", "Title2"]
                ) or (
                    "Editor" in [r.name for r in user.roles]
                    and post_title[i] in ["Title3", "Title4"]
                ):
                    post_details = {
                        "title": post_title[i],
                        "content": post_content[i],
                        "user_id": user.id,
                    }

                    post = Post(**post_details)
                    db.session.add(post)

            db.session.commit()


from .model import Permission, Post, Role, User
