from __future__ import annotations

import json as JSON

import click
from flask import current_app
from flask.cli import with_appcontext


@click.command("rpbac-audit", help="Shows routes protected by rpbac")
@click.option(
    "--verbose", "-v", "verbose", is_flag=True, help="Show detailed information"
)
@click.option(
    "-u",
    "unprotected",
    is_flag=True,
    help="Echos routes that are not protected by RPBAC",
)
@click.option(
    "-a",
    "all",
    is_flag=True,
    help="Echos all routes protected or unprotected by RPBAC",
)
@click.option(
    "--json",
    "json",
    is_flag=True,
    help="Echo in a JSON format",
)
@with_appcontext
def rpbac_route_requirements(verbose: bool, unprotected: bool, all: bool, json: bool):
    """A very basic function, triggered from the terminal to get protected routes and their roles and permissions"""

    _ROUTES = []
    _SUMMARY = {"routes_scanned": 0, "protected": 0, "unprotected": 0}

    for rule in current_app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue

        route = current_app.view_functions.get(rule.endpoint)

        if route is None:
            continue

        route_requirement = getattr(route, "_rpbac_requirements", None)
        bp_requirements = getattr(route, "_rpbac_bp_requirements", None)

        blueprint_name = rule.endpoint.split(".")[0] if "." in rule.endpoint else None

        # Echos only unprotected routes
        if unprotected:
            if route_requirement is None and bp_requirements is None:
                if json:
                    build_json_data(
                        rule.endpoint,
                        rule.rule,
                        rule.methods,
                        bp_requirements,
                        route_requirement,
                        blueprint_name,
                        _ROUTES,
                        _SUMMARY,
                        verbose=verbose,
                        protected=False,
                    )
                else:
                    echo_un_routes(rule.rule, rule.methods)
            continue

        # Echos both protected and unprotected routes
        if all:
            if route_requirement is None and bp_requirements is None:
                if json:
                    build_json_data(
                        rule.endpoint,
                        rule.rule,
                        rule.methods,
                        bp_requirements,
                        route_requirement,
                        blueprint_name,
                        _ROUTES,
                        _SUMMARY,
                        verbose=verbose,
                        protected=False,
                    )
                else:
                    echo_un_routes(rule.rule, rule.methods, verbose=verbose)
            elif (bp_requirements and route_requirement) or (
                route_requirement and not bp_requirements
            ):
                if json:
                    build_json_data(
                        rule.endpoint,
                        rule.rule,
                        rule.methods,
                        bp_requirements,
                        route_requirement,
                        blueprint_name,
                        _ROUTES,
                        _SUMMARY,
                        verbose=verbose,
                        protected=True,
                    )
                else:
                    echo_rpbac_pro_routes(
                        blueprint_name,
                        rule.methods,
                        rule.rule,
                        bp_requirements,
                        route_requirement,
                        verbose=verbose,
                    )
            continue

        # For endpoints that are protected by rpbac
        # By defaults, without the -u or -p flag, the audit shows
        # only routes that are protectd by rpbac.
        if (bp_requirements and route_requirement) or (
            route_requirement and not bp_requirements
        ):
            if json:
                build_json_data(
                    rule.endpoint,
                    rule.rule,
                    rule.methods,
                    bp_requirements,
                    route_requirement,
                    blueprint_name,
                    _ROUTES,
                    _SUMMARY,
                    verbose=verbose,
                    protected=True,
                )
            else:
                echo_rpbac_pro_routes(
                    blueprint_name,
                    rule.methods,
                    rule.rule,
                    bp_requirements,
                    route_requirement,
                    verbose=verbose,
                )

    if len(_ROUTES) > 0:
        data = {"summary": _SUMMARY, "findings": _ROUTES}

        json_data = JSON.dumps(data, indent=2)

        click.echo(json_data)


# Command helper functions
def echo_rpbac_pro_routes(
    bp_name: str | None,
    methods: set[str] | None,
    endpoint: str,
    bp_req: str | None,
    route_req: str,
    *,
    verbose=False,
):
    """
    Handles echoing rpbac route audit feature. This is be used only for
    route with either bp req or route req or both.

    Args:
        bp_name (str | None): The name of the blueprint
        methods (set[str] | None): Methods to the endpoint
        endpoint (str): The endpoint URL
        bp_req (str | None): Blueprint requirement policy to the route
        route_req (str): Route requirement policy
        verbose (bool): Determine to include more information about a route
    """
    if bp_req is not None:
        if verbose:
            click.echo(
                f"{bp_name} {list(methods if methods else ['GET'])} {endpoint:30} -> {bp_req} {route_req}"
            )
        else:
            click.echo(f"{bp_name} {endpoint:30} -> {bp_req} {route_req}")

    else:
        if verbose:
            click.echo(
                f"{list(methods if methods else ['GET'])} {endpoint:30} -> {route_req}"
            )
        else:
            click.echo(f"{endpoint:30} -> {route_req}")


def echo_un_routes(endpoint: str, methods: set[str] | None, *, verbose=False):
    """
    Echose endpoints that are not protected by rpbac.

    Args:
        endpoint (str): The endpoint URL
        methods (set[str] | None): Methods to the endpoint
        verbose (bool): Determine to include more information about a route
    """
    if verbose:
        click.echo(f"{list(methods if methods else ['GET'])} -> {endpoint:30}")
    else:
        click.echo(f"{endpoint:30}")


def build_json_data(
    view: str,
    endpoint: str,
    methods: set[str] | None,
    bp_req: str | None,
    route_req: str | None,
    bp_name: str | None,
    routes: list[dict],
    summary: dict[str, int],
    *,
    verbose: bool = False,
    protected: bool = True,
):
    """
    Builds a JSON body of routes with their neccessary information.

    Args:
        routes (list[dict]): A list of routes
    """
    summary["routes_scanned"] += 1

    if protected:
        summary["protected"] += 1

        data = {
            "rule": endpoint,
            "bp_name": bp_name,
            "bp_req": f"{bp_req}",
            "route_req": f"{route_req}",
        }
        if verbose:
            data.update(
                {
                    "methods": list(methods) if methods else ["GET"],
                    "view": view,
                }
            )

        routes.append(data)

    else:
        summary["unprotected"] += 1

        data = {
            "rule": endpoint,
        }
        if verbose:
            data.update(
                {
                    "methods": list(methods) if methods else ["GET"],
                    "view": view,
                }  # pyright: ignore
            )

        routes.append(data)
