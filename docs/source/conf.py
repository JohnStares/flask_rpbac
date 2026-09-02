# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

project = "Flask-RPBAC"
copyright = "2026, John Stares"
author = "John Stares"

release = "1.0"
version = "1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosectionlabel",
]

templates_path = ["_templates"]
exclude_patterns = []

master_doc = "index"

language = "en"

html_static_path = ["_static"]
html_theme_path = ["/home/john-stares/Desktop/VS Code/projects/rpbac/.venv/lib/python3.14/site-packages/flask_sphinx_themes"]
html_theme = "flask"
html_theme_options = {"github_fork": "JohnStares/Humantic"}
html_title = "Flask-RPBAC"
html_short_title = "Flask-RPBAC"
html_show_sphinx = False

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_use_param = True
napoleon_use_rtype = True

# Keep the doc build clear and consistent for modern Python projects.
pygments_style = "sphinx"



