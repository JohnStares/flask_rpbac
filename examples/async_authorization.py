"""Demonstrate async views, async authorization loaders, and async predicates.

Run with ``python examples/async_authorization.py`` after installing the project
and its dependencies. Replace the demo identity and in-memory data functions with
your application's authentication and asynchronous data-access services.
"""

from __future__ import annotations

import asyncio

from flask import Flask, jsonify

from flask_rpbac import RPBAC, All, Any, Not, Permission, Predicate, Role

app = Flask(__name__)
# The memory cache keeps the example self-contained. In production, configure
# Redis or another shared cache if caching authorization data is appropriate.
rpbac = RPBAC(app, cache_config={"type": "memory"})

# Demo data standing in for an asynchronous repository or ORM.
POSTS = {
    1: {"id": 1, "author_id": "user-1", "title": "Owned post", "archived": False},
    2: {
        "id": 2,
        "author_id": "user-2",
        "title": "Another user's post",
        "archived": True,
    },
}


async def authenticated_user_id() -> str:
    """Replace with an async call to your application's identity provider."""
    await asyncio.sleep(0)
    return "user-1"


async def get_post(post_id: int) -> dict | None:
    """Replace with an async database or service lookup."""
    await asyncio.sleep(0)
    return POSTS.get(post_id)


@rpbac.load_user_identity
async def load_user_identity() -> str:
    # This stable identity is used as the cache key when caching is enabled.
    return await authenticated_user_id()


@rpbac.user_data_loader
async def load_user_data() -> dict[str, list[str]]:
    """Return both authorization collections in one asynchronous callback."""
    user_id = await authenticated_user_id()
    # Replace these example values with roles and permissions loaded for user_id.
    return {
        "roles": ["editor"] if user_id == "user-1" else [],
        "permissions": ["post:read", "post:write"] if user_id == "user-1" else [],
    }


@app.get("/dashboard")
@rpbac.required(All(Role("editor"), Permission("post:read")))
async def dashboard():
    """An async view using ordinary composed role and permission checks."""
    return jsonify({"message": "Editor dashboard"})


async def can_edit_post(ctx) -> bool:
    """Check ownership asynchronously using the current route's post_id."""
    post_id = ctx.kwargs["post_id"]
    post = await get_post(post_id)
    user_id = await authenticated_user_id()
    return post is not None and post["author_id"] == user_id


async def is_archived(ctx) -> bool:
    """Check an object-state condition for use inside a Not requirement."""
    post = await get_post(ctx.kwargs["post_id"])
    return post is not None and post["archived"]


@app.patch("/posts/<int:post_id>")
@rpbac.required(
    Any(
        Role("admin"),
        All(Permission("post:write"), Predicate(can_edit_post)),
    )
)
async def edit_post(post_id: int):
    """Use Any/All to combine static checks with an async ownership predicate."""
    post = await get_post(post_id)
    if post is None:
        return jsonify({"error": "not_found"}), 404

    # The demo update is intentionally simple; persist changes through your
    # application's async repository or ORM in a real application.
    post["title"] = "Updated title"
    return jsonify({"message": "Post updated", "post": post})


@app.get("/posts/<int:post_id>/preview")
@rpbac.required(Not(Predicate(is_archived)))
async def preview_post(post_id: int):
    """Use Not to reject the request when an async state predicate passes."""
    post = await get_post(post_id)
    if post is None:
        return jsonify({"error": "not_found"}), 404

    return jsonify({"post": post})


if __name__ == "__main__":
    app.run(debug=True)
