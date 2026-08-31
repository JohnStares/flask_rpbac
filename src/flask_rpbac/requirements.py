from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import RPBAC, RPBACBuildContext

from .exc import RPBACError, RPBACPermissionError, RPBACRoleError


class Requirements:
    """
    Base class for all requirement types in the RBAC system.
    Provides operator overloading for combining requirements using AND (&) and OR (|) logic.
    """

    def check(self, ctx):
        """Check if the requirement passes for the given context.

        Args:
            ctx: The build context containing user roles and permissions.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError

    def escalate(self, rpbac: RPBAC):
        """Escalate privilege loading for this requirement.

        Args:
            rbac: The RBAC instance to escalate loaders on.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError

    def __and__(self, other):
        return All(self, other)

    def __or__(self, other):
        return Any(self, other)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}"


class All(Requirements):
    """
    Requirement that passes only when ALL child requirements pass.
    Combines multiple requirements with AND logic. If any requirement fails,
    the entire check fails.
    """

    def __init__(self, *reqs: Requirements):
        """Initialize with multiple requirements.

        Args:
            *reqs (Requirements): Variable number of Requirements objects to combine.
        """
        self.reqs = reqs

    def check(self, ctx):
        """Check all requirements sequentially.

        Args:
            ctx: The build context containing user roles and permissions.

        Returns:
            bool: True if all requirements pass.

        Raises:
            RPBACError: If any requirement fails.
        """
        for r in self.reqs:
            r.check(ctx)

        return True

    def escalate(self, rpbac: RPBAC):
        """Escalate all child requirements."""
        for req in self.reqs:
            req.escalate(rpbac)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(repr(r) for r in self.reqs)})"


class Any(Requirements):
    """Requirement that passes when AT LEAST ONE child requirement passes.
    Combines multiple requirements with OR logic. Checks requirements in order
    and returns True on the first successful check.
    """

    def __init__(self, *reqs: Requirements) -> None:
        """Initialize with multiple requirements.

        Args:
            *reqs (Requirements): Variable number of Requirements objects to combine.
        """
        self.reqs = reqs

    def check(self, ctx):
        """Check requirements until one passes.

        Args:
            ctx: The build context containing user roles and permissions.

        Returns:
            bool: True if at least one requirement passes.

        Raises:
            RPBACError: If all requirements fail (re-raises the last error).
        """
        last_error = None

        for r in self.reqs:
            try:
                r.check(ctx)
                return True

            except RPBACError as e:
                last_error = e

        if last_error is not None:
            raise last_error

    def escalate(self, rpbac: RPBAC):
        """Escalate all child requirements."""
        for req in self.reqs:
            req.escalate(rpbac)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(repr(r) for r in self.reqs)})"


class Role(Requirements):
    """Requirement that checks if a user has specific roles.
    Supports checking for 'any' of the listed roles or 'all' of them.
    """

    def __init__(self, *roles: str, match: str = "any") -> None:
        """Initialize with role requirements.

        Args:
            *roles (str): Variable number of role names to check.
            match (str): Matching strategy - "any" (default) or "all".
                  "any": User needs at least one of the roles.
                  "all": User needs all of the roles.
        """
        self.roles = roles
        self.match = match

    def check(self, ctx: RPBACBuildContext):
        """Check if user has the required roles.

        Args:
            ctx (RPBACBuildContext): The build context containing user roles.

        Returns:
            bool: True if role requirements are met.

        Raises:
            RPBACRoleError: If the user doesn't have the required roles.
        """
        user_roles = set(ctx.roles)

        passed = (
            (user_roles & set(self.roles))
            if self.match == "any"
            else set(self.roles).issubset(user_roles)
        )

        if not passed:
            raise RPBACRoleError(required=self.roles, granted=user_roles)

        return True

    def escalate(self, rpbac: RPBAC):
        """Escalate role loaders for this requirement."""
        rpbac._escalate_role_loaders()

    def __repr__(self) -> str:
        roles = ", ".join(repr(r) for r in self.roles)

        return f"{self.__class__.__name__}({roles}, match={self.match})"


class Permission(Requirements):
    """Requirement that checks if a user has specific permissions.
    Supports checking for 'all' of the listed permissions or 'any' of them.
    """

    def __init__(self, *permissions: str, match: str = "all") -> None:
        """Initialize with permission requirements.

        Args:
            *permissions (str): Variable number of permission names to check.
            match (str): Matching strategy - "all" (default) or "any".
                  "all": User needs all of the permissions.
                  "any": User needs at least one of the permissions.
        """
        self.permissions = permissions
        self.match = match

    def check(self, ctx: RPBACBuildContext):
        """Check if user has the required permissions.

        Args:
            ctx (RPBACBuildContext): The build context containing user permissions.

        Returns:
            bool: True if permission requirements are met.

        Raises:
            RPBACPermissionError: If the user doesn't have the required permissions.
        """
        user_permissions = set(ctx.permissions)

        passed = (
            set(self.permissions).issubset(user_permissions)
            if self.match == "all"
            else bool(user_permissions & set(self.permissions))
        )

        if not passed:
            raise RPBACPermissionError(
                required=self.permissions, granted=user_permissions
            )

        return True

    def escalate(self, rpbac: RPBAC):
        """Escalate permission loaders for this requirement."""
        rpbac._escalate_perm_loaders()

    def __repr__(self) -> str:
        perm = ", ".join(repr(r) for r in self.permissions)

        return f"{self.__class__.__name__}({perm}, match={self.match})"
