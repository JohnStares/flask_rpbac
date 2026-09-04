Flask-RPBAC
===========

.. image:: https://github.com/JohnStares/flask_rpbac/actions/workflows/tests.yml/badge.svg
   :target: https://github.com/JohnStares/flask_rpbac/actions/workflows/tests.yml
   :alt: Test status

.. image:: https://codecov.io/github/JohnStares/flask_rpbac/graph/badge.svg?token=MILHOWADRP 
    :target: https://codecov.io/github/JohnStares/flask_rpbac
    :alt: Code coverage


Flask-RPBAC is a lightweight Flask authorization extension for expressing role-based and
permission-based access control in a clean, composable way. It is designed for applications that
need explicit access checks without turning authorization logic into a large set of ad hoc
conditionals.

For the full documentation, including installation, quick start, API reference, and examples,
please see the project docs on Read the Docs: https://flask-rpbac.readthedocs.io/en/latest/

The library supports:

- role-based access checks
- permission-based access checks
- combined authorization rules with ``All`` and ``Any``
- composable requirement objects using ``&`` and ``|`` operators
- blueprint-level protection alongside route-level protection
- loader callbacks for roles, permissions, and user data

What it does
------------

Flask-RPBAC lets you define authorization rules in a declarative style and apply them to Flask
routes or entire blueprints. This keeps access decisions readable, testable, and easy to evolve as
an application grows.

Typical use cases include:

- restricting admin-only endpoints
- enforcing permission checks for resource actions
- combining role and permission requirements for complex policies
- protecting blueprint sections with general access rules while keeping route-specific rules

Quick example
-------------

.. code-block:: python

   from flask import Flask
   from flask_login import current_user
   from flask_rpbac import RPBAC, Role, Permission, All, Any

   app = Flask(__name__)
   rpbac = RPBAC(app)

   @rpbac.role_loader
   def load_roles():
       return ["admin", "editor"] if current_user.is_authenticated else []

   @rpbac.permission_loader
   def load_permissions():
       return ["post:read", "post:write"] if current_user.is_authenticated else []

   @app.route("/admin")
   @rpbac.role_required(Role("admin"))
   def admin_panel():
       return "Admin panel"

   @app.route("/publish")
   @rpbac.required(All(Role("editor"), Permission("post:write")))
   def publish_post():
       return "Publish"

   @app.route("/shared")
   @rpbac.required(Any(Role("admin"), Permission("post:read")))
   def shared_view():
       return "Shared view"

Installation
------------

Install the package with pip:

.. code-block:: bash

   pip install flask_rpbac

Requirements
------------

Flask-RPBAC targets modern Flask applications and is designed for Flask 3.1 and newer, with
Python 3.12+ support.

Contributing
------------

Contributions are welcome. Please read the `full contribution guide
<.github/CONTRIBUTING.md>`_ before opening a pull request.

We encourage pull requests, issue reports, and improvements to documentation, tests, and access
control examples. A healthy contribution workflow is:

- open an issue or discussion for larger changes
- keep changes focused and easy to review
- add or update tests for behavior changes
- keep the public API clear and consistent
- update documentation when user-facing behavior changes
- follow the project coding and testing standards already in place

Before submitting changes, please run the project test suite and ensure the relevant checks pass.
If you are improving behavior, add a regression test so the change is protected in the future.

Useful contributor resources:

- `Contribution guide <.github/CONTRIBUTING.md>`_
- `Code of Conduct <.github/CODE_OF_CONDUCT.md>`_
- `Security Policy <.github/SECURITY.md>`_
- `Issue templates <.github/ISSUE_TEMPLATE/>`_
- `Full documentation <https://flask-rpbac.readthedocs.io/en/latest/>`_

Before submitting a change, contributors should have Python 3.12 or newer, create a virtual
environment, install the development dependencies, and verify the project locally:

.. code-block:: bash

    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    pytest
    tox

Please report security vulnerabilities privately through the process described in the
`Security Policy <.github/SECURITY.md>`_, rather than opening a public issue.

License
-------

This project is distributed under the terms of the repository's license.
