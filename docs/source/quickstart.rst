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

``@rpbac.load_user_identity``
    Loads the identity of the currently logged-in user. When caching is enabled, this identity is
    used as the cache key for that user's roles and permissions. It is a separate callback from
    ``user_data_loader``.

These decorators are meant to return data for the currently logged-in user only. In practice,
that data usually comes from your database, an ORM model, a cache, or another user-store layer.

Example:

.. code-block:: python

   from flask_login import current_user
   from flask_rpbac import RPBAC

   rpbac = RPBAC()

   @rpbac.load_user_identity
   def load_user_identity():
       # Return the current user's stable, unique identifier.
       return current_user.id

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
       # Use one efficient query to fetch both authorization collections for the current user.
       # The user identity is provided separately by load_user_identity above.
       roles, permissions = query_user_roles_and_permissions(current_user.id)
       return {
           "roles": roles, # A list or set
           "permissions": permissions, # A list or set
       }

The loaders are separate from the decorators that protect routes. This keeps route checks
focused on authorization rules and keeps user identity resolution and authorization-data loading
in dedicated callbacks. ``user_data_loader`` does not provide the cache identity; use
``load_user_identity`` for that purpose.

Caching user authorization data
-------------------------------

To cache a user's roles and permissions in memory, pass a memory cache configuration and register
``load_user_identity``. The identity callback must return a stable value that uniquely identifies
the current user. The cache is keyed by that value, so different users receive separate cached
authorization contexts.

.. code-block:: python

   rpbac = RPBAC(app, cache_config={"type": "memory"})

   @rpbac.load_user_identity
   def load_user_identity():
       return current_user.id

The cache is optional. If no cache configuration is supplied, the identity loader is not used for
caching and the role or permission loaders run for each request context. The in-memory cache is
intended as a starting implementation and should not be used as a production replacement for a
durable shared cache.

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
``All``, ``Any``, and ``Not`` to express complex authorization rules.

``All`` means every requirement must pass.
``Any`` means at least one requirement must pass.
``Not`` means the wrapped requirement must not pass. A requirement that raises an
``RPBACError`` is considered to have failed, so ``Not`` turns that failure into a
successful check. If the wrapped requirement passes, ``Not`` raises an
``RPBACNegationError``.

There is also an important internal rule for the individual requirement classes:

- ``Role("admin", "editor", match="any")`` means the user needs at least one of those roles.
- ``Role("admin", "editor", match="all")`` means the user must have all of those roles.
- ``Permission("edit_post", "publish_post", match="all")`` means all listed permissions are required.
- ``Permission("edit_post", "publish_post", match="any")`` means any one of them is enough.

That means the internal ``match`` option is already built into ``Role`` and ``Permission``
for same-type checks. ``All`` and ``Any`` are especially useful when combining different
requirement types or building nested logic. ``Not`` is useful for exclusions and for
expressing the inverse of an existing requirement without writing a new predicate.

Negating requirements
~~~~~~~~~~~~~~~~~~~~~~

Use ``Not`` with one requirement when access should be granted only if that
requirement fails:

.. code-block:: python

   from flask_rpbac import Not, Permission, Role

   @app.route("/non-admin-area")
   @rpbac.required(Not(Role("admin")))
   def non_admin_area():
       return "Available to users without the admin role"

   @app.route("/without-delete-access")
   @rpbac.required(Not(Permission("post:delete")))
   def without_delete_access():
       return "Available to users without post:delete"

In these examples, a user who has the excluded role or permission receives a
``403`` response. A user who does not have it is allowed through. ``Not`` does
not suppress unrelated application exceptions from a predicate or loader; only
``RPBACError`` failures count as a failed authorization requirement.

``Not`` can also wrap a ``Predicate``. A predicate that returns ``True`` passes
normally, so ``Not(Predicate(...))`` returns ``False`` and denies the request.
A predicate that returns ``False`` raises ``RPBACPredicateError``, so ``Not``
turns that failure into ``True`` and allows the request:

.. code-block:: python

   def is_owner(ctx):
       post = load_post(ctx.kwargs["post_id"])
       return post is not None and post.author_id == current_user.id

   @app.route("/posts/<int:post_id>/not-owned")
   @rpbac.required(Not(Predicate(is_owner)))
   def not_owned(post_id):
       return "This post belongs to somebody else"

The ``/not-owned`` route is allowed when ``is_owner`` returns ``False`` and
denied when it returns ``True``. This is useful for exclusion rules based on
request-specific data, such as preventing an owner from using an endpoint or
allowing access only when a resource does not match a condition. An unexpected
exception raised inside the predicate is still propagated and is not treated as
a normal predicate failure.

``Not`` accepts multiple requirements. This form means that none of the listed
requirements may pass:

.. code-block:: python

   @app.route("/not-staff")
   @rpbac.required(Not(Role("admin"), Role("moderator")))
   def not_staff():
       return "Available to users who are neither admins nor moderators"

Under the hood, ``Not(Role("admin"), Permission("post:delete"))`` has the
same logic as ``Not(Any(Role("admin"), Permission("post:delete")))``. Both
requirements must fail for the ``Not`` requirement to pass. This is the right
form when access must exclude anyone with *either* capability:

.. code-block:: python

   @app.route("/regular-users-only")
   @rpbac.required(Not(Role("admin"), Permission("billing:manage")))
   def regular_users_only():
       return "Available to users without admin or billing access"

Use ``Not(All(...))`` when you want to reject only users who satisfy the whole
combination. It passes when at least one child requirement fails:

.. code-block:: python

   @app.route("/not-fully-approved")
   @rpbac.required(
       Not(
           All(
               Role("editor"),
               Permission("post:publish"),
           )
       )
   )
   def not_fully_approved():
       return "Available to users who are not fully approved to publish"

Here, a user with both the ``editor`` role and ``post:publish`` permission is
denied. A user with only one of them, or neither, is allowed. This differs from
``Not(Role("editor"), Permission("post:publish"))``:

* ``Not(All(Role("editor"), Permission("post:publish")))`` denies users with
  both capabilities and allows partial matches.
* ``Not(Role("editor"), Permission("post:publish"))`` denies users with either
  capability and allows only users with neither capability.

Choose ``Not(Any(...))`` or multiple arguments to exclude every listed
requirement. Choose ``Not(All(...))`` to exclude only users who satisfy the
entire combination. For positive rules, continue to use ``All`` and ``Any``
directly because they communicate the allowed capability more clearly.

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

Static checks and object-level checks
-------------------------------------

Role and permission requirements are static checks: they answer whether the current user has a
role or permission that applies to a route in general. That is the right model for endpoints such
as an admin dashboard or a page that any editor may read, but it is not enough for a rule such as
"an editor may update only their own post". A user can have the ``post:write`` permission and
still be forbidden from changing a particular object.

``Predicate`` adds a request-scoped check for those cases. A predicate receives an
``RPBACBuildContext`` containing:

``ctx.roles``
    The roles returned by the configured role or user-data loader.

``ctx.permissions``
    The permissions returned by the configured permission or user-data loader.

``ctx.kwargs``
    The keyword arguments captured by Flask's route, such as ``post_id`` or ``user_id``.

The route decorator passes these URL arguments into the context before evaluating the requirement.
This keeps the normal role and permission loaders focused on user-wide authorization data, while a
predicate can make the final decision using the specific resource addressed by the request.

For example, the following rule permits a user to edit a post only when they own it:

.. code-block:: python

   from flask import Flask
   from flask_login import current_user
   from flask_rpbac import RPBAC, Predicate

   app = Flask(__name__)
   rpbac = RPBAC(app)

   def can_edit_post(ctx):
       post = Post.query.get(ctx.kwargs["post_id"])
       return post is not None and post.author_id == current_user.id

   @app.route("/posts/<int:post_id>/edit", methods=["POST"])
   @rpbac.required(Predicate(can_edit_post))
   def edit_post(post_id):
       return "Post updated"

The predicate is evaluated before ``edit_post`` runs. It can load the object using the captured
identifier, compare it with the current user, and return ``True`` or ``False``. A false result
raises ``RPBACPredicateError`` and is handled using the same rejection behavior as role and
permission failures.

You can use the same pattern for read and delete operations. The predicate does not need to query
the database itself; it may call a repository or service function that returns the authorization
decision:

.. code-block:: python

   def can_read_invoice(ctx):
       invoice_id = ctx.kwargs["invoice_id"]
       return invoice_service.user_can_read(current_user.id, invoice_id)

   @app.route("/invoices/<int:invoice_id>")
   @rpbac.required(Predicate(can_read_invoice))
   def invoice(invoice_id):
       return render_invoice(invoice_id)

   def can_delete_comment(ctx):
       comment = Comment.query.get(ctx.kwargs["comment_id"])
       return comment is not None and comment.author_id == current_user.id

   @app.delete("/comments/<int:comment_id>")
   @rpbac.required(Predicate(can_delete_comment))
   def delete_comment(comment_id):
       delete_comment_from_database(comment_id)
       return "Deleted"

Predicates can also enforce tenant or organization boundaries. Route arguments may contain more
than one identifier, so the predicate can ensure that both the parent and child object belong to
the same tenant:

.. code-block:: python

   def can_view_project_file(ctx):
       return project_file_service.belongs_to_tenant(
           file_id=ctx.kwargs["file_id"],
           tenant_id=ctx.kwargs["tenant_id"],
           user_id=current_user.id,
       )

   @app.route("/tenants/<tenant_id>/files/<int:file_id>")
   @rpbac.required(Predicate(can_view_project_file))
   def project_file(tenant_id, file_id):
       return send_file_for_download(file_id)

For sharing-based authorization, the predicate can check a relationship instead of ownership. This
keeps a user's static permissions separate from the list of individual resources they can access:

.. code-block:: python

   def can_view_document(ctx):
       document_id = ctx.kwargs["document_id"]
       return document_service.has_access(
           user_id=current_user.id,
           document_id=document_id,
       )

   @app.route("/documents/<uuid:document_id>")
   @rpbac.required(Predicate(can_view_document))
   def document(document_id):
       return render_document(document_id)

The lookup should return ``False`` for a missing object or an unauthorized relationship. Do not
rely on the view to perform the check after it has already loaded or modified the resource.

Dynamic permissions from route kwargs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some applications encode the resource or tenant directly in the permission name. For example,
the permissions loaded for a user might contain ``"jane_blog:edit_post"`` and
``"team_blog:read_post"``. RPBAC does not try to guess whether an application uses a
``<resource>:<action>``, ``<tenant>:<resource>:<action>``, or another permission format. The
application owns that naming convention and can use a ``Predicate`` to translate route kwargs into
the permission name it wants to check.

For a route such as ``/blogs/jane_blog/posts/42/edit``, the predicate can build
``jane_blog:edit_post`` from ``ctx.kwargs["blog_name"]`` and check it against
``ctx.permissions``:

.. code-block:: python

   def can_edit_post_in_blog(ctx):
       blog_name = ctx.kwargs["blog_name"]
       required_permission = f"{blog_name}:edit_post"
       return required_permission in ctx.permissions

   @app.route("/blogs/<blog_name>/posts/<int:post_id>/edit", methods=["POST"])
   @rpbac.required(Predicate(can_edit_post_in_blog))
   def edit_post(blog_name, post_id):
       return "Post updated"

If the request is for ``/blogs/jane_blog/posts/42/edit``, the predicate checks whether
``"jane_blog:edit_post"`` is present in the current user's permissions. A request for
``team_blog`` instead checks ``"team_blog:edit_post"``. The permission loader remains responsible
for loading the user's permission collection; the predicate only derives the request-specific name
and performs the check.

The same approach works when the naming scheme has multiple parts. Keep the construction in a
named function so the policy is easy to test and so normalization is explicit:

.. code-block:: python

   def can_manage_blog_settings(ctx):
       tenant = ctx.kwargs["tenant"]
       blog_name = ctx.kwargs["blog_name"]
       permission = f"{tenant}:{blog_name}:manage_settings"
       return permission in ctx.permissions

   @app.route("/tenants/<tenant>/blogs/<blog_name>/settings", methods=["POST"])
   @rpbac.required(Predicate(can_manage_blog_settings))
   def manage_blog_settings(tenant, blog_name):
       return "Settings updated"

If names are case-insensitive or allow aliases, normalize the route values before constructing the
permission. For example, use ``blog_name.casefold()`` if the loader stores lowercase names. Do not
silently convert identifiers if that could make two distinct resources share a permission name.
The predicate should return ``False`` when a required kwarg is absent or when the derived name is
not in ``ctx.permissions``; for a fixed route shape, direct indexing such as
``ctx.kwargs["blog_name"]`` is appropriate and makes a misconfigured route visible.

Dynamic and static permissions can be required together. This is useful when a user needs both a
general capability and access to the particular blog named by the request:

.. code-block:: python

   def can_edit_named_blog(ctx):
       permission = f"{ctx.kwargs['blog_name']}:edit_post"
       return permission in ctx.permissions

   @app.route("/blogs/<blog_name>/posts/<int:post_id>/edit", methods=["POST"])
   @rpbac.required(
       All(
           Permission("post:write"),
           Predicate(can_edit_named_blog),
       )
   )
   def edit_named_blog_post(blog_name, post_id):
       return "Post updated"

An administrator override can be expressed with the same requirement composition:

.. code-block:: python

   @rpbac.required(
       Any(
           Role("admin"),
           All(Permission("post:write"), Predicate(can_edit_named_blog)),
       )
   )
   def edit_named_blog_post(blog_name, post_id):
       return "Post updated"

Using ``Role.identifier_from_kwargs``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Role.identifier_from_kwargs(kwarg_name)`` is a convenience requirement for one specific data
model: the route identifier is stored in the current user's loaded roles. It creates a
``Predicate`` that evaluates whether ``ctx.kwargs[kwarg_name]`` is present in ``ctx.roles``.

For example, an application may load the account IDs a support user is allowed to access as role
values, then protect an account route like this:

.. code-block:: python

   @rpbac.role_loader
   def load_roles():
       # This application represents accessible account IDs as role values.
       return account_service.accessible_account_ids(current_user.id)

   @app.route("/accounts/<account_id>")
   @rpbac.required(Role.identifier_from_kwargs("account_id"))
   def account(account_id):
       return render_account(account_id)

If the loader returns ``["account-123", "account-456"]``, the first route is allowed and an
account such as ``account-999`` is rejected. The route keyword name must match the argument passed
to ``identifier_from_kwargs``. The route value and loaded role value must also use compatible types;
for an integer route such as ``<int:account_id>``, return integers from the role loader rather than
strings.

This helper is useful for a direct identifier-to-access-list check, but it is not a general role
hierarchy or object relationship system. Use ``Predicate`` when access depends on ownership,
tenant membership, sharing, object state, or a database relationship. The helper also assumes the
key exists in the route kwargs; use a matching route or a custom predicate when the URL shape is
optional or varies.

Predicates are ordinary requirements, so they can be composed with static checks. For example,
this allows an administrator to edit any post while other users may edit only their own:

.. code-block:: python

   from flask_rpbac import All, Any, Permission, Predicate, Role

   post_editor = All(
       Permission("post:write"),
       Predicate(can_edit_post),
   )

   @app.route("/posts/<int:post_id>/edit", methods=["POST"])
   @rpbac.required(Any(Role("admin"), post_editor))
   def edit_post(post_id):
       return "Post updated"

Another common pattern is to require a static permission for the action and a predicate for the
object relationship. This makes the policy explicit: the user must be allowed to perform the
action and must be allowed to perform it on this particular object.

.. code-block:: python

   @app.route("/projects/<int:project_id>/settings", methods=["POST"])
   @rpbac.required(
       All(
           Permission("project:manage"),
           Predicate(
               lambda ctx: project_service.is_manager(
                   current_user.id, ctx.kwargs["project_id"]
               )
           ),
       )
   )
   def update_project_settings(project_id):
       return "Settings updated"

Why this approach
-----------------

The extension keeps two kinds of authorization data separate. Loaders provide stable,
user-specific facts such as roles and permissions, while predicates evaluate request-specific facts
such as a URL identifier, a tenant, or the relationship between a user and a database object.
That separation avoids putting every possible object into a user's static permission set and makes
the policy visible at the route where it is enforced.

Predicates should remain small and deterministic. If a check needs a database lookup, load only the
object or relationship needed for the decision, and return ``False`` when the object does not exist
or the user cannot access it. Keep mutations in the view rather than in the predicate.

Choosing Flask-RPBAC
--------------------

Several Flask extensions can participate in authorization, but they solve different problems. The
following is a practical guide rather than a claim that one library replaces all of the others.

``Flask-Principal``
    Choose it when you want a flexible identity, need, and permission system that can be integrated
    into a broader Flask application. It is a good foundation for applications that want to model
    authorization primitives themselves. Choose Flask-RPBAC when you want route decorators and
    readable ``Role``/``Permission``/``All``/``Any`` requirement trees out of the box, together
    with predicates that receive Flask route arguments.

``Flask-Security``
    Choose it when you need a broader security solution including authentication workflows, user
    registration, password handling, roles, permissions, and related account features. Choose
    Flask-RPBAC when authentication is already handled by Flask-Login or another system and the
    missing piece is a small, explicit authorization layer, especially for per-object checks.

``Flask-RBAC``
    Choose it when your application primarily needs conventional role-based access checks and its
    role model and decorators fit your existing code. Choose Flask-RPBAC when authorization rules
    need composable role and permission logic, blueprint-level protection, or request/object-level
    predicates using route kwargs.

In short, use Flask-RPBAC for authorization close to Flask routes: static role and permission
checks for broad access, combined requirements for policy composition, and ``Predicate`` when the
decision depends on the particular object named by the request. Use Flask-Security for the larger
authentication and account-management problem, Flask-Principal for a lower-level needs model, or
Flask-RBAC for a simpler role-only approach that already matches your application.

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
