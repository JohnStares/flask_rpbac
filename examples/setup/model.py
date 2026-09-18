from __future__ import annotations

import sqlalchemy as sql
from sqlalchemy import orm
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, jwt

user_roles = sql.Table(
    "user_roles",
    db.metadata,
    sql.Column("id", sql.Integer, primary_key=True, index=True),
    sql.Column("user_id", sql.ForeignKey("users.id", ondelete="CASCADE"), index=True),
    sql.Column("role_id", sql.ForeignKey("roles.id", ondelete="CASCADE"), index=True),
    sql.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
)

role_permissions = sql.Table(
    "role_permissions",
    db.metadata,
    sql.Column("id", sql.Integer, primary_key=True, index=True),
    sql.Column("role_id", sql.ForeignKey("roles.id", ondelete="CASCADE"), index=True),
    sql.Column(
        "permission_id",
        sql.ForeignKey("permissions.id", ondelete="CASCADE"),
        index=False,
    ),
    sql.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
)


class User(db.Model):
    __tablename__ = "users"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)
    name: orm.Mapped[str] = orm.mapped_column(sql.String(20), unique=True, index=True)
    email: orm.Mapped[str] = orm.mapped_column(sql.String(50), unique=True, index=True)

    _hashed_password: orm.Mapped[str] = orm.mapped_column(
        sql.String(355), nullable=True
    )

    roles: orm.Mapped[list[Role]] = orm.relationship(
        "Role", secondary=user_roles, back_populates="users"
    )

    def hash_password(self, password: str | None) -> None:
        """Hashes a users password"""
        if password is None:
            raise ValueError("Password cannot be None")

        self._hashed_password = generate_password_hash(password)

    def compare_hashed_password(self, password: str) -> bool:
        """Compared the provided password against the stored hashed password"""
        return check_password_hash(self._hashed_password, password)

    def get_roles(self):
        """Gets all roles of a user"""
        stmt = (
            sql.select(Role.name)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == self.id)
        )

        roles = db.session.scalars(stmt).all()

        return roles

    def get_permissions(self):
        """Get all permissions of a user"""
        stmt = (
            sql.select(Permission.name)
            .distinct()
            .select_from(User)
            .join(user_roles, user_roles.c.user_id == User.id)
            .join(Role, user_roles.c.role_id == Role.id)
            .join(role_permissions, Role.id == role_permissions.c.role_id)
            .join(Permission, role_permissions.c.permission_id == Permission.id)
            .where(User.id == self.id)
        )

        permissions = db.session.scalars(stmt).all()

        return permissions

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}::{self.name}"


class Role(db.Model):
    __tablename__ = "roles"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)
    name: orm.Mapped[str] = orm.mapped_column(sql.String(25), unique=True, index=True)

    users: orm.Mapped[list[User]] = orm.relationship(
        "User", secondary=user_roles, back_populates="roles"
    )

    permissions: orm.Mapped[list[Permission]] = orm.relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}::{self.name}"


class Permission(db.Model):
    __tablename__ = "permissions"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)
    name: orm.Mapped[str] = orm.mapped_column(sql.String(20), unique=True, index=True)

    roles: orm.Mapped[list[Role]] = orm.relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}::{self.name}"


class Post(db.Model):
    __tablename__ = "posts"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)
    title: orm.Mapped[str] = orm.mapped_column(sql.String(20), unique=True, index=True)
    content: orm.Mapped[str] = orm.mapped_column(sql.Text, index=True)

    user_id: orm.Mapped[int] = orm.mapped_column(
        sql.ForeignKey("users.id", ondelete="CASCADE", name="fk_user_post_id"),
        index=True,
    )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}::Title: {self.title}"


@jwt.user_identity_loader
def user_identity_loader(user: User):
    return f"{user.id}"
