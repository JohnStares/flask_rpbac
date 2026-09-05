Quick Start
===========

This section walks through the minimal setup for a Flask application that uses
Flask-RPBAC to protect routes, blueprints, and template logic.

The important distinction is this:

- app creation and initialization is separate from
- loading the user's roles and permissions
- and from applying route-level authorization rules

This separation keeps the authorization logic explicit and easy to test.

Creating and initializing the app
---------------------------------

The first step is to create a Flask app and bind the extension to it.

.. code-block:: python

   from flask import Flask
   from flask_rpbac import RPBAC

   app = Flask(__name__)
   rpbac = RPBAC(app)

You can also initialize the extension later in a factory function:

.. code-block:: python

   from flask import Flask
   from flask_rpbac import RPBAC

   rpbac = RPBAC()

   def create_app():
       app = Flask(__name__)
       rpbac.init_app(app)
       return app

The loader decorators
---------------------

After the app is initialized, you tell RPBAC how to discover the current user state.
These are the loader decorators and each one has a different responsibility:

``@rpbac.role_loader``
    Loads the current user's roles. Use it when roles are stored separately or can be
    fetched via a small helper function.

``@rpbac.permission_loader``
    Loads the current user's permissions. Use it when permissions are fetched independently
    from the user's roles.

``@rpbac.user_data_loader``
    Loads both roles and permissions in one callback. This is useful when a single query or
    cached lookup returns all authorization data for the request context.

These decorators are meant to return data for the currently logged-in user only. In practice,
that data usually comes from your database, an ORM model, a cache, or another user-store layer.

Example:

.. code-block:: python

   from flask_login import current_user
   from flask_rpbac import RPBAC

   rpbac = RPBAC()

   @rpbac.role_loader
   def load_roles():
       # Data can come from your database, ORM, cache, or any other storage layer.
       # The return result must be a list or set of roles
       user_id = current_user.id
       return fetch_user_roles(user_id) # {"admin", "editor"} or ["admin", "editor"]

   @rpbac.permission_loader
   def load_permissions():
       # Data can come from your database, ORM, cache, or any other storage layer.
       # The return result mist a list or set of permissions
       user_id = current_user.id
       return fetch_user_permissions(user_id) # {"post:read", "post:delete"} or ["post:read", "post:delete"]

   @rpbac.user_data_loader
   def load_user_data():
       # Best practice: use one efficient query to fetch the currently logged-in user
       # by user_id = current_user.id, then return both the roles and permissions in one dictionary.
       # The dictionary should have keys: id, roles, permissions.
       user_id = current_user.id
       roles, permissions = query_user_roles_and_permissions(user_id)
       return {
           "id": user_id, # A string
           "roles": roles, # A list or set
           "permissions": permissions, # A list or set
       }

The loaders are separate from the decorators that protect routes. This keeps route checks
focused on authorization rules and leaves user identity resolution in dedicated loader functions.

Protecting routes
-----------------

Flask-RPBAC provides three route-level decorator entry points:

``role_required``
    Use when a route should be guarded by a role requirement only.

``permission_required``
    Use when a route should be guarded by a permission requirement only.

``required``
    Use when you want a custom composition of role and permission checks, or when you need a
    more complex nested authorization rule.

Examples:

.. code-block:: python

   from flask_rpbac import RPBAC, Role, Permission, All, Any

   app = Flask(__name__)
   rpbac = RPBAC(app)

   @app.route("/admin")
   @rpbac.role_required(Role("admin"))
   def admin_panel():
       return "Administrator panel"

   @app.route("/posts")
   @rpbac.permission_required(Permission("post:read"))
   def posts():
       return "Post list"

   @app.route("/dashboard")
   @rpbac.required(All(Role("editor"), Permission("post:write")))
   def dashboard():
       return "Dashboard"

The key idea is that the decorator decides which authorization rule to evaluate, while the loader
only supplies the current user data.

Handling authorization errors
------------------------------

When a protected route rejects a request, Flask-RPBAC raises an ``RPBACError``. You can choose
how that error is handled in one of three ways.

1. Let Flask-RPBAC provide the default response

This is the default behavior. When ``raise_generic_error`` is ``False`` and no rejection hook is
configured, Flask-RPBAC registers an internal Flask error handler for ``RPBACError``. A rejected
request receives a ``403`` JSON response similar to:

.. code-block:: json

    {
         "error": "forbidden",
         "message": "..."
    }

No additional configuration is required:

.. code-block:: python

    app = Flask(__name__)
    rpbac = RPBAC(app)

2. Handle ``RPBACError`` yourself

Set ``raise_generic_error=True`` when you want the exception to propagate instead of using the
package's default Flask error handler. This lets your application register its own Flask error
handler or handle the error through its broader exception-management strategy.

.. code-block:: python

    app = Flask(__name__)
    rpbac = RPBAC(app, raise_generic_error=True)

    @app.errorhandler(RPBACError)
    def handle_rpbac_error(error):
         return {"error": "access_denied", "message": str(error)}, 403

3. Return a custom response with a rejection hook

A rejection hook is a function that runs whenever a role or permission requirement is denied.
The hook receives the ``RPBACError`` and must return the response your Flask route should send.
You can provide it in the constructor or in the init_app:

.. code-block:: python

    def handle_rejection(error):
         return {"error": "forbidden", "reason": str(error)}, 403

    app = Flask(__name__)
    rpbac = RPBAC(app, rejection_hook=handle_rejection)

You can also register the hook with the ``@rpbac.rejection_hook`` decorator:

.. code-block:: python

    app = Flask(__name__)
    rpbac = RPBAC(app)

    @rpbac.rejection_hook
    def handle_rejection(error):
         return {"error": "forbidden", "reason": str(error)}, 403

The decorator registration replaces a rejection hook previously supplied to the RPBAC instance.
When a rejection hook is configured, it takes precedence over the default Flask error handler.
The same rejection behavior applies to route-level and blueprint-level protection.

Composable rules
----------------

The real strength of the package is in composition. You can combine checks using
``All`` and ``Any`` to express complex authorization rules.

``All`` means every requirement must pass.
``Any`` means at least one requirement must pass.

There is also an important internal rule for the individual requirement classes:

- ``Role("admin", "editor", match="any")`` means the user needs at least one of those roles.
- ``Role("admin", "editor", match="all")`` means the user must have all of those roles.
- ``Permission("edit_post", "publish_post", match="all")`` means all listed permissions are required.
- ``Permission("edit_post", "publish_post", match="any")`` means any one of them is enough.

That means the internal ``match`` option is already built into ``Role`` and ``Permission``
for same-type checks. ``All`` and ``Any`` are especially useful when combining different
requirement types or building nested logic.

Typical patterns:

1. Single role or single permission

.. code-block:: python

   @app.route("/profile")
   @rpbac.role_required(Role("user"))
   def profile():
       return "Profile"

   @app.route("/edit-post")
   @rpbac.permission_required(Permission("edit_post"))
   def edit_post():
       return "Edit post"

2. Multiple roles with "any" semantics

.. code-block:: python

   @app.route("/moderation")
   @rpbac.required(Role("admin", "moderator", match="any"))
   def moderation():
       return "Moderation panel"

   @app.route("/moderation-alt")
   @rpbac.required(Any(Role("admin"), Role("moderator")))
   def moderation_alt():
       return "Moderation panel"

3. Multiple permissions with "all" semantics

.. code-block:: python

   @app.route("/publish")
   @rpbac.required(Permission("edit_post", "publish_post", match="all"))
   def publish():
       return "Publish"

   @app.route("/publish-alt")
   @rpbac.required(All(Permission("edit_post"), Permission("publish_post")))
   def publish_alt():
       return "Publish"

4. Role and permission together

.. code-block:: python

   @app.route("/dashboard")
   @rpbac.required(All(Role("editor"), Permission("post:write")))
   def dashboard():
       return "Dashboard"

5. Admin override pattern

.. code-block:: python

   @app.route("/admin-override")
   @rpbac.required(
       Any(
           Role("admin"),
           All(Role("editor"), Permission("delete_own_post")),
       )
   )
   def admin_override():
       return "Admin override"

6. Different role/permission combos granting access

.. code-block:: python

   @app.route("/special-actions")
   @rpbac.required(
       Any(
           All(Role("editor"), Permission("publish_post")),
           All(Role("moderator"), Permission("flag_post")),
       )
   )
   def special_actions():
       return "Special actions"

The requirement objects also support the overloaded ``&`` and ``|`` operators, which make the
same logic read naturally:

.. code-block:: python

   requirement_a = Role("admin") & Permission("post:write")
   requirement_b = Role("admin") | Permission("report:view")

   @app.route("/combined-a")
   @rpbac.required(requirement_a)
   def combined_a():
       return "Combined A"

   @app.route("/combined-b")
   @rpbac.required(requirement_b)
   def combined_b():
       return "Combined B"

   complex_rule = (
       Role("editor") & Permission("post:write")
   ) | (
       Role("admin") & Permission("report:view")
   )

   @app.route("/complex")
   @rpbac.required(complex_rule)
   def complex_access():
       return "Complex access"

This produces the same logic as nested ``All`` and ``Any`` objects, but often with a more compact
and readable style.

Template access checks
----------------------

If you enable the context processor, the extension exposes helper objects in Jinja templates.
This is useful for displaying or hiding UI elements conditionally.

.. code-block:: html

   {% if rpbac.has_role("admin") %}
     <a href="/admin">Admin</a>
   {% endif %}

   {% if rpbac.can(All(Role("admin"), Permission("post:write"))) %}
     <button>Publish</button>
   {% endif %}

Blueprint protection
--------------------

You can protect an entire blueprint at once:

.. code-block:: python

   from flask import Blueprint

   admin_bp = Blueprint("admin_bp", __name__)

   rpbac.protect_blueprint(admin_bp, Role("admin"))

   @admin_bp.route("/settings")
   def settings():
       return "Settings"

   @admin_bp.route("/audit")
   def audit():
       return "Audit log"


This applies the given requirement to every route on the blueprint. The important behavior is that
it does not interfere with route-level protection; instead, blueprint-level rules and route-level
rules are combined and both are executed.

Example:

.. code-block:: python

   from flask import Blueprint
   from flask_rpbac import Role, Permission, All

   editor_bp = Blueprint("editor_bp", __name__)

   rpbac.protect_blueprint(editor_bp, Role("editor"))

   @editor_bp.route("/posts")
   @rpbac.permission_required(Permission("post:read"))
   def posts():
       return "Posts"

   @editor_bp.route("/publish")
   @rpbac.required(All(Role("editor"), Permission("post:write")))
   def publish():
       return "Publish"


In this example, the blueprint-level rule requires an editor role for all routes, while the route
itself also enforces additional permission or role checks. Both checks are evaluated together.

Another example:

.. code-block:: python

   from flask import Blueprint
   from flask_rpbac import Role, Permission, Any

   support_bp = Blueprint("support_bp", __name__)

   @support_bp.route("/tickets")
   @rpbac.required(Any(Role("support"), Permission("ticket:view")))
   def tickets():
       return "Tickets"

   rpbac.protect_blueprint(support_bp, Role("staff"))

The route still has its own requirement, but the blueprint rule is evaluated alongside it instead
of replacing it. This is useful when you want a general access guard for a whole section of the
application and still enforce route-specific constraints.

CLI auditing
------------

The extension includes a CLI command for reviewing protected routes:

.. code-block:: bash

   export FLASK_APP=<appname>
   
   flask rpbac-audit

This helps inspect which routes are protected and what requirements they enforce.
