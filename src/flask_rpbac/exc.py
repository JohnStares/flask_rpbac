class RPBACError(Exception):
    """Base class for RBAC Errors"""


class RPBACPermissionError(RPBACError):
    """Raises Errors caused by invalid Permissions"""

    def __init__(self, required, granted) -> None:
        self.required = set(required)
        self.granted = set(granted)
        super().__init__(f"Missing permission(s): {self.required - self.granted}")


class RPBACRoleError(RPBACError):
    """Raises Errors caused by invalid Roles"""

    def __init__(self, required, granted) -> None:
        self.required = set(required)
        self.granted = set(granted)
        super().__init__(f"Missing role(s): {self.required - self.granted}")


class RPBACPredicateError(RPBACError):
    """Raises Errors caused by failed callable"""

    def __init__(self, func, ctx) -> None:
        self.func = func
        self.ctx = ctx
        super().__init__(f"Authz Failed: {self.func.__name__} - {self.ctx}")
