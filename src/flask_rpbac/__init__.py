from __future__ import annotations

import warnings
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING

from flask import g, jsonify, request

if TYPE_CHECKING:
    from flask import Blueprint, Flask

    from .requirements import Requirements

from .exc import RPBACError, RPBACPermissionError, RPBACRoleError
from .requirements import All, Any, Permission, Role

__all__ = [
    "RPBAC",
    "All",
    "Any",
    "Permission",
    "RPBACError",
    "RPBACPermissionError",
    "RPBACRoleError",
    "Role",
]


class RPBACBuildContext:
    """A snapshot object of the current users roles or permissions"""

    def __init__(self, roles=None, permissions=None) -> None:
        self.roles = roles or set()
        self.permissions = permissions or set()


class RPBAC:
    """
    An object used to hold settings and callback functions for the flask
    RPBAC extension. Instance of :class:`RPBAC` are *not* bound to specific
    apps, therefore, you can create one in the main body of your code and then
    bind it to your app in a factory function
    """

    def __init__(self, app: Flask | None = None, **kwargs):
        """
        Create the RPBAC instance. There are two ways to initialze RPBAC::

            app = Flask(__name__)
            rpbac = RPBAC(app)

        or::

            rpbac = RPBAC()

            def create_app():
                app = Flask(__name__)
                rpbac.init_app(app)
                return app

        Args:
            app (Flask | None, optional): The Flask instance. Defaults to None.
        """
        # This controls whether rpbac should be available in jinja templates
        self.add_context_processor = kwargs.get("add_context_processor", True)
        self.raise_generic_error = kwargs.get("raise_generic_error", False)
        self._rejection_hook = kwargs.get("rejection_hook")

        self._permission_loader_callback = None
        self._role_loader_callback = None
        self._user_role_perm_loader_callback = None

        # Hold the requirements of a blueprint that is protected by rpbac
        self.__blueprint_requirements = {}

        # Register this extension with the flask app now if it is provided
        if app is not None:
            self.init_app(app, **kwargs)
        else:
            self.app = None

    def init_app(self, app: Flask, **kwargs):
        """
        Initialize flask app in RPBAC

        Args:
            app (Flask): The flask instance
        """
        self.app = (
            app  # Track the flask app, will be used to know if flask app is registered
        )

        self.add_context_processor = kwargs.get("add_context_processor", True)
        self.raise_generic_error = kwargs.get("raise_generic_error", False)
        self._rejection_hook = kwargs.get("rejection_hook")

        if not hasattr(app, "extensions"):
            app.extensions = {}

        app.extensions["rpbac"] = self

        if self.add_context_processor:
            app.context_processor(self._inject_rpbac)

        self.__app_exc_handler(app)

        self.__register_all_cli_commands(app)

    def role_required(self, role_requirements: Role) -> Callable:
        """
        Decorate a route so it only allows access when the required roles match.

        Example::

            @app.route("/admin")
            @rpbac.role_required(Role("admin", match="any"))
            def admin_panel():
                return "Admin panel"

        Args:
            role_requirements (Role): The required role combination for the route.
        """
        return self.required(role_requirements)

    def permission_required(self, permission_requirements: Permission) -> Callable:
        """
        Decorate a route so it only allows access when the required permissions match.

        Example::

            @app.route("/posts")
            @rpbac.permission_required(Permission("post:read", match="all"))
            def posts():
                return "Post list"

        Args:
            permission_requirements (Permission): The required permission combination for the route.
        """

        return self.required(permission_requirements)

    def required(self, requirements: Requirements) -> Callable:
        """
        A decorator that protects a route with roles and permissions of different
        combinations by combining composable classes.\n

        Usage::

            @rpbac.required(All(Role("editor"), Permission("publish_post")))
            or
            @rpbac.require(Any(Role("admin"), All(Role("editor"), Permission("delete_own_post"))))

        Any of the examples above can be used depending on the use case. Sophisticated roles and permissions
        requirements can be achieved by combining these classes in one line rather than stacking separate
        decorators on a route.

        Args:
            requirements (Requirements): A class that represents all composable first-class objects.
        """

        def decorator(func: Callable):
            # Store requirement metadata on function itself
            func._rpbac_requirements = requirements  # pyright: ignore

            @wraps(func)
            def wrapper(*args, **kwargs):

                # Each requirement class checks and escalates if its loader callback is not configured before trying to call the callback
                requirements.escalate(self)
                ctx = self.__build_context()

                blueprint_requirements = self.__blueprint_requirements.get(
                    request.blueprint
                )
                combined = (
                    All(blueprint_requirements, requirements)
                    if blueprint_requirements
                    else requirements
                )
                try:
                    combined.check(ctx)
                except RPBACError as e:
                    if self._rejection_hook is not None:
                        return self._rejection_hook(e)

                    raise

                return func(*args, **kwargs)

            wrapper._rpbac_requirements = requirements  # pyright: ignore

            return wrapper

        return decorator

    def permission_loader(self, func: Callable):
        """
        This decorator sets the callback function used to get the permissions
        of a user that will be used in a protected route.\n

        It is recommened the returned permissons are a set or list of permissions
        that will match that provided in the route

        Returns:
            _type_: A set or list of permissions
        """
        self._permission_loader_callback = func

        return func

    def role_loader(self, func: Callable):
        """
        This decorator sets the callback function used to get the roles
        of a user that will be used in a protected route.\n

        It is recommened the returned roles are a set or list of roles
        that will match that provided in the route

        Returns:
            _type_: A set or list of roles
        """
        self._role_loader_callback = func

        return func

    def user_data_loader(self, func):
        """
        This decorator sets the callback function used to get the user id, role and
        permissions that will be used in the protected route. This is useful when the role
        and permissions are to be gotten with a single efficent query and also for caching
        of roles and permissions of a user (that is where the user id comes in).\n

        It is recommended that the returned value be a dictionary. Example::

            return {
                "id": f"{user_id}",
                "roles": [roles] or {roles},
                "permissions": [permissions] or {permissions}
            }

        Returns:
            _type_: A dictionary of user id, roles and permissions
        """
        self._user_role_perm_loader_callback = func

        return func

    def rejection_hook(self, func: Callable):
        """
        This decorator sets the callback function that returns a custom
        error message for both Role and Permission rejection.

        NOTE: This overwrites any other rejection hook set at the
            construction level

        Returns:
            _type_: An error response
        """
        if self._rejection_hook is not None:
            warnings.warn(
                "Overwriting an already registered RPBAC error handler.", stacklevel=2
            )

        self._rejection_hook = func
        return func

    def can(self, requirements: Requirements) -> bool:
        """
        This method provides a convenient way of checking of roles and permissions using
        the composable classes in jinja templating.

        Usage::

            {% if rpbac.can(All(Role("Admin"), Any(Role("Editor"), Permission("post:edit", "post:delete")))) %}
                # Do something here ...
            {% endif %}

        Args:
            requirements (Requirements): A class that represents all composable first-class objects.

        Returns:
            bool: True if the requirements passes else False
        """
        try:
            requirements.escalate(self)
            ctx = self.__build_context()
            requirements.check(ctx)
            return True

        except RPBACError:
            return False

    def has_permission(self, *permission: str) -> bool:
        """
        This method provides a convenient way of checking for permissions only
        in jinja templates.

        Usage::

            {% if rpbac.has_permission("post:edit", "post:delete") %}
                # Do something here
            {% endif %}

        Returns:
            bool: A True if the permission requiremnts passes else False
        """
        return self.can(Permission(*permission))

    def has_role(self, *role: str) -> bool:
        """
        This method provides a convenient way of checking for roles only
        in jinja templates.

        Usage::

            {% if rpbac.has_role("Admin", "Editor") %}
                # Do something here
            {% endif %}

        Returns:
            bool: A True if the role requirements passes else False
        """
        return self.can(Role(*role))

    def protect_blueprint(self, blueprint: Blueprint, requirements: Requirements):
        """
        When called, it protects routes at a blueprint level. This ensures that all
        route of a blueprint are protected using just that particular requirements.\n

        This doesn't interfer with route level protection, rather both protection
        are combined and executed.

        Usage::

            from flask import Blueprint

            admin_bp = Blueprint("admin_bp", __name__)

            rpbac.protect_blueprint(admin_bp, Role("Admin"))

        Args:
            blueprint (Blueprint): The Flask Blueprint instance
            requirements (Requirements): A class that represents all composable first-class objects.

        """

        self.__blueprint_requirements[blueprint.name] = requirements

        # Store a reference of the blueprint
        original_blueprint_add_url_rule = blueprint.add_url_rule

        def wrapped_route(rule: str, **options):
            def decorator(func: Callable):
                if not getattr(func, "_rpbac_wrapped", False):
                    original_func = getattr(func, "_original", func)

                    @wraps(func)
                    def wrapper(*args, **kwargs):
                        requirements.escalate(self)
                        ctx = self.__build_context()

                        try:
                            requirements.check(ctx)
                        except RPBACError as e:
                            if self._rejection_hook is not None:
                                return self._rejection_hook(e)

                            raise

                        return original_func(*args, **kwargs)

                    wrapper._rpbac_bp_requirements = requirements  # pyright: ignore
                    wrapper._rpbac_wrapped = True  # pyright: ignore
                    wrapper._original = original_func  # pyright: ignore
                    func = wrapper

                endpoint = options.get("endpoint")
                original_blueprint_add_url_rule(rule, endpoint, func, **options)

                return func

            return decorator

        blueprint.route = wrapped_route  # pyright: ignore

    # Helper methods
    def __build_context(self):
        """
        Responsible for fetching roles and permissions from
        the callback and bulding a fresh snapshot with it on every request,
        making in available to use within a single request context and shipping
        it off to the required decorator.


        Returns:
            _type_: Any | RPBACBuildContext
        """

        if hasattr(g, "_rpbac_context"):
            return g._rpbac_context

        if self._user_role_perm_loader_callback is not None:
            data = self._user_role_perm_loader_callback()

            roles = data["roles"]
            permissions = data["permissions"]

            ctx = RPBACBuildContext(roles=roles, permissions=permissions)

            g._rpbac_context = ctx
            return ctx

        if self._role_loader_callback is not None:
            roles = self._role_loader_callback()
        else:
            roles = None

        if self._permission_loader_callback is not None:
            permissions = self._permission_loader_callback()
        else:
            permissions = None

        ctx = RPBACBuildContext(roles=roles, permissions=permissions)

        g._rpbac_context = ctx
        return ctx

    def _inject_rpbac(self):
        """Properties that will be injected into jinja templating"""
        return {
            "rpbac": {
                "can": self.can,
                "has_permission": self.has_permission,
                "has_role": self.has_role,
            },
            "All": All,
            "Any": Any,
            "Role": Role,
            "Permission": Permission,
        }

    def __app_exc_handler(self, app: Flask):
        """Registered RPBACError(s) to flask for proper exception handling"""

        if not self.raise_generic_error and self._rejection_hook is None:
            app.register_error_handler(RPBACError, self.__default_error_response)

    def __default_error_response(self, error: RPBACError):
        """Default error returned if no error handler is registered."""
        return jsonify({"error": "forbidden", "message": str(error)}), 403

    def __escalate(self) -> None:
        """Raises an error if flask app is not initialized"""
        assert self.app, "Please initialize your application into flask RPBAC"

    def _escalate_role_loaders(self) -> None:
        """Raises an error is no roles loader of any sort is configured"""
        self.__escalate()
        if (
            self._user_role_perm_loader_callback is None
            and self._role_loader_callback is None
        ):
            raise RuntimeError(
                "No role_loader configured. Use @rpbac.user_data_loader or @rpbac.role_loader "
                "to configure one"
            )

    def _escalate_perm_loaders(self) -> None:
        """Raises an error if no permissions loader of any sort is configured"""
        self.__escalate()
        if (
            self._user_role_perm_loader_callback is None
            and self._permission_loader_callback is None
        ):
            raise RuntimeError(
                "No permission_loader configured. Use @rpbac.user_data_loader or @rpbac.permission_loader "
                "to configure one"
            )

    def __register_all_cli_commands(self, app: Flask):
        """Registers all cli commands to flask app"""

        from .cli import rpbac_route_requirements

        app.cli.add_command(rpbac_route_requirements)
