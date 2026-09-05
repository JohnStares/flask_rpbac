API Reference
=============

This reference documents the public API exposed by Flask-RPBAC.

Core extension
--------------

.. automodule:: src.flask_rpbac
   :members:
   :undoc-members:
   :show-inheritance:

Requirements and checks
-----------------------

.. automodule:: src.flask_rpbac.requirements
   :members:
   :undoc-members:
   :show-inheritance:

Exceptions
----------

The package exposes the public exception types through the main import surface:

- ``RPBACError``
- ``RPBACPermissionError``
- ``RPBACRoleError``

These are defined in the exception module and raised when a route or blueprint check fails.

CLI command
-----------

.. automodule:: src.flask_rpbac.cli
   :members:
   :undoc-members:
   :show-inheritance:

Authorization model
-------------------

The extension is centered around a simple pattern:

1. Load the current user identity with ``load_user_identity`` and load roles and permissions with
    ``role_loader``, ``permission_loader``, or ``user_data_loader``.
2. Construct a request-scoped context.
3. Evaluate a requirement tree made from ``Role``, ``Permission``, ``All``, and ``Any``.
4. Raise a structured exception when access is denied.

When caching is configured, the value returned by ``load_user_identity`` is used as the cache key.
The ``user_data_loader`` callback supplies roles and permissions only; it does not supply the
cache identity.

This keeps the access-control rules declarative and consistent throughout the application.

Public types
------------

``RPBAC``
    Main extension class used to initialize the app and register authorization hooks.

``Role``
    Represents a role requirement. It can check for any or all matches.

``Permission``
    Represents a permission requirement. It can check for any or all matches.

``All``
    Combines multiple requirements with logical AND semantics.

``Any``
    Combines multiple requirements with logical OR semantics.

``RPBACError``
    Base exception for authorization failures.

``RPBACRoleError``
    Raised when a required role is missing.

``RPBACPermissionError``
    Raised when a required permission is missing.
