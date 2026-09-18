Why Flask-RPBAC?
================

Flask-RPBAC is a focused authorization extension for Flask applications. It provides roles,
permissions, composable requirements, and contextual predicates without imposing an authentication
system, database, ORM, or user model on your application.

The goal is deliberately narrow: your application identifies the user, loads the authorization
data it trusts, and Flask-RPBAC evaluates whether that data satisfies a policy. It is useful when
you want authorization rules close to Flask routes without adopting a complete security or identity
framework.

Authentication and authorization
--------------------------------

Authentication answers:

    Who is this user?

Authorization answers:

    What is this user allowed to do?

These responsibilities are related but different. An application may already use Flask-Login, JWT
authentication, a custom session system, an API gateway, or another identity provider. It may also
use SQLAlchemy, MongoDB, Redis, a remote service, or no database at all.

Flask-RPBAC does not replace those components. Its loaders let the application provide the current
user's identity, roles, permissions, or combined user data, while the requirement system evaluates
access.

The problem with scattered authorization checks
------------------------------------------------

Authorization often starts with simple checks:

.. code-block:: python

   if current_user.is_admin:
       ...

   if "post:update" in current_user.permissions:
       ...

   if post.author_id == current_user.id:
       ...

Those checks can be perfectly reasonable in a small application. As an application grows,
authorization logic can become scattered across views, blueprints, services, and resource-specific
code. Policies also become more involved: a rule may require a role, a permission, ownership,
tenant membership, an object state, or an administrator override.

Flask-RPBAC gives those decisions a named, composable representation that can be applied to routes
and blueprints and tested independently from the view body.

Composable authorization requirements
-------------------------------------

A simple role or permission requirement can be expressed as:

.. code-block:: python

   Role("admin")
   Permission("post:update")

Requirements can be combined using ``All`` and ``Any`` or the ``&`` and ``|`` operators:

.. code-block:: python

   Permission("post:update") & Predicate(is_owner)

   Role("admin") | (
       Permission("post:update") & Predicate(is_owner)
   )

The first policy requires both the operation permission and the object check. The second allows an
administrator, or a user with the operation permission who also owns the resource. The same policy
can be written with ``All`` and ``Any`` when that is clearer for a larger requirement tree.

``Not`` can express exclusion rules when the application needs to deny a known role or condition:

.. code-block:: python

   Permission("reports:view") & Role("suspended")

The exact policy model remains an application decision. Flask-RPBAC does not require every project
to represent authorization in the same way.

Contextual and object-level authorization
-----------------------------------------

Many decisions cannot be made from a role or permission alone. A user may edit only their own post,
a manager may access resources belonging to their department, or a request may need a permission
whose name is derived from a route argument.

``Predicate`` receives an ``RPBACBuildContext`` containing the loaded roles and permissions plus
the route keyword arguments in ``ctx.kwargs``:

.. code-block:: python

   def can_edit_post(ctx):
       post = Post.query.get(ctx.kwargs["post_id"])
       return post is not None and post.author_id == current_user.id

   @app.route("/posts/<int:post_id>", methods=["POST"])
   @rpbac.required(Permission("post:update") & Predicate(can_edit_post))
   def edit_post(post_id):
       return "Updated"

The extension cannot infer an application's object model, tenant model, or permission naming
scheme. For example, if permissions are stored as ``"jane_blog:edit_post"``, the application can
translate a route argument into that name explicitly:

.. code-block:: python

   def can_edit_blog_post(ctx):
       permission = f"{ctx.kwargs['blog_name']}:edit_post"
       return permission in ctx.permissions

   @rpbac.required(Predicate(can_edit_blog_post))
   def edit_blog_post(blog_name, post_id):
       return "Updated"

This keeps application-specific policy decisions in application code while allowing them to
participate in the same requirement composition as static role and permission checks.

What Flask-RPBAC deliberately does not provide
----------------------------------------------

Flask-RPBAC is not an authentication framework or user-management system. It does not require:

* a particular authentication library;
* a particular ``User`` class;
* SQLAlchemy or another ORM;
* a database or session implementation;
* JWT or Flask-Login;
* a specific persistence layer.

It also does not automatically discover ownership, tenant membership, resource state, or the
meaning of a permission string. Those are application-specific concerns. A predicate can connect
those concerns to a requirement, but the application must define and maintain the underlying logic.

Roles and permissions
---------------------

Roles are useful for broad responsibilities or positions:

.. code-block:: python

   Role("billing_manager")

Permissions are useful for specific operations:

.. code-block:: python

   Permission("invoice:approve")

Applications can use either model independently or combine them. A permission can also be dynamic
when its name includes a route value, but the application must construct and validate that name in a
predicate rather than expecting the extension to guess its format.

Blueprint and route protection
------------------------------

Flask-RPBAC can protect individual routes or entire blueprints. Blueprint requirements and route
requirements are combined, so a blueprint can provide a broad guard while a route adds a more
specific permission or predicate.

This is useful when protected areas should be visible at the routing layer. Detailed resource
checks can still live in small predicates or in a service layer called by a predicate.

A separation of concerns
------------------------

A typical application can be organized like this:

.. code-block:: text

   Authentication
       |
       | Establishes the current identity
       v
   Application data loaders
       |
       | Provides roles, permissions, and user data
       v
   Flask-RPBAC
       |
       | Evaluates the authorization policy
       v
   Protected route or operation

This separation allows authentication and authorization to evolve independently. For example, an
application can change from session-based authentication to token-based authentication without
rewriting its authorization requirements, provided the loaders continue to supply the needed data.

When Flask-RPBAC is a good fit
------------------------------

Flask-RPBAC may fit well when your application:

* already has authentication and needs a focused authorization layer;
* needs route or blueprint protection;
* uses roles, permissions, or both;
* needs object-level or contextual checks;
* needs policies composed from multiple requirements;
* has administrator overrides or conditional access rules;
* wants to keep its existing ORM, database, user model, and identity provider;
* wants authorization logic that can be tested independently of view code.

It is especially useful when authorization has outgrown a single decorator or an inline condition,
but adopting a larger security framework would add more than the application needs.

When another solution may be more appropriate
----------------------------------------------

Flask-RPBAC may not be the right choice if you need a complete authentication and security suite
that provides user registration, password management, login and logout views, email confirmation,
password recovery, session management, or user administration. A broader security extension may be
more appropriate in that situation.

It may also be a poor fit when authorization is centralized in a policy service, requires a
specialized policy language, or must be shared across many non-Flask services. A general-purpose
authorization engine or a dedicated policy service may better match those requirements.

Comparison with related Flask extensions
----------------------------------------

The choice depends on the problem being solved:

``Flask-Principal``
    A lower-level identity, need, and permission foundation. It can be a good choice when the
    application wants to model its own authorization primitives and integration flow. Flask-RPBAC
    is more opinionated about route decorators and composable requirement objects, and includes a
    request context for predicates.

``Flask-Security``
    A broader security solution for applications that need authentication workflows, account
    management, passwords, roles, and permissions together. Flask-RPBAC is a better fit when
    authentication already exists and the missing requirement is a small, explicit authorization
    layer.

``Flask-RBAC``
    A conventional role-based access approach. It may be sufficient when straightforward role
    checks match the application's needs. Flask-RPBAC is worth considering when the application
    needs composable roles and permissions, blueprint protection, or object-level predicates.

These are not mutually exclusive architectural ideas, and no extension removes the need for the
application to define its security policy. Choose the smallest tool that matches the requirements,
and prefer a broader security suite or centralized policy system when those are the actual needs.

Next steps
----------

Start with the :doc:`quickstart` to configure Flask-RPBAC. Then explore roles, permissions,
composed requirements, predicates, dynamic permissions, object-level authorization, blueprint
protection, and custom data loaders. For the complete API, see the :doc:`api_reference` reference.
