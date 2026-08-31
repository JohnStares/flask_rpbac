from __future__ import annotations

import click
from flask import current_app
from flask.cli import with_appcontext


@click.command("rpbac-audit", help="Shows routes protected by rpbac")
@click.option(
    "--verbose", "-v", "verbose", is_flag=True, help="Show detailed information"
)
@with_appcontext
def rpbac_route_requirements(verbose):
    """A very basic function, triggered from the terminal to get protected routes and their roles and permissions"""
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue

        route = current_app.view_functions.get(rule.endpoint)

        if route is None:
            continue

        route_requirement = getattr(route, "_rpbac_requirements", None)
        bp_requirements = getattr(route, "_rpbac_bp_requirements", None)

        blueprint_name = rule.endpoint.split(".")[0] if "." in rule.endpoint else None

        if bp_requirements and route_requirement:
            if verbose:
                click.echo(
                    f"{blueprint_name} {list(rule.methods if rule.methods else ['GET'])} {rule.rule:30} -> {bp_requirements} {route_requirement}"
                )
            else:
                click.echo(
                    f"{blueprint_name} {rule.rule:30} -> {bp_requirements} {route_requirement}"
                )

        if route_requirement and not bp_requirements:
            if verbose:
                click.echo(
                    f"{list(rule.methods if rule.methods else ['GET'])} {rule.rule:30} -> {route_requirement}"
                )
            else:
                click.echo(f"{rule.rule:30} -> {route_requirement}")
