Flask-RPBAC
===========

Flask-RPBAC is a lightweight role- and permission-based access control extension for Flask.
It gives you a clean way to enforce authorization rules directly on routes, blueprints,
and Jinja templates using composable requirements such as ``Role``, ``Permission``, ``All``,
and ``Any``.

The library is designed to fit naturally into Flask applications without requiring a large
framework or custom middleware stack. It integrates with your existing request lifecycle and
keeps authorization logic explicit, readable, and easy to test.

Key features
------------

- Role and permission checks for Flask routes
- Composable authorization rules with ``All`` and ``Any``
- Blueprint-level protection support
- Simple Jinja helpers for template-level checks
- CLI inspection for protected routes via ``rpbac-audit``
- Built for modern Flask application patterns

.. toctree::
   :maxdepth: 2
   :caption: Documentation

   installation
   quickstart
   api_reference

Quick example
-------------

.. code-block:: python

   from flask import Flask
   from flask_rpbac import RPBAC, Role, Permission, All, Any

   app = Flask(__name__)
   rpbac = RPBAC(app)

   @rpbac.role_loader
   def load_roles():
       return ["admin", "editor"]

   @rpbac.permission_loader
   def load_permissions():
       return ["post:read", "post:write"]

   @app.route("/dashboard")
   @rpbac.required(All(Role("admin"), Permission("post:write")))
   def dashboard():
       return "Welcome to the dashboard"

   @app.route("/reports")
   @rpbac.required(Any(Role("admin"), Permission("report:view")))
   def reports():
       return "Reports"

This package is intended for applications that want explicit authorization logic while remaining
small, testable, and easy to reason about.

