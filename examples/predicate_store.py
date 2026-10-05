"""Share a loaded resource between authorization predicates with ``ctx.pstore``.

Run from the repository root with Flask-RPBAC installed. The in-memory records
stand in for a database or service repository.
"""

from __future__ import annotations

import asyncio

from flask import Flask, jsonify

from flask_rpbac import RPBAC, All, Any, Predicate, Role

app = Flask(__name__)
rpbac = RPBAC(app)


@rpbac.role_loader
def load_roles() -> list[str]:
    return []


POSTS = {
    1: {"id": 1, "author_id": "user-1", "blog_id": 10},
    2: {"id": 2, "author_id": "user-2", "blog_id": 10},
}
BLOGS = {10: {"id": 10, "owner_id": "user-1"}}
query_counts = {"posts": 0, "blogs": 0}


def current_user_id() -> str:
    """Substitute the identity established by your authentication system."""
    return "user-1"


def load_post(ctx) -> bool:
    """Fetch once and make the post available to later predicates."""
    query_counts["posts"] += 1
    post = POSTS.get(ctx.kwargs["post_id"])
    if post is None:
        return False

    ctx.pstore["post"] = post
    return True


def load_blog_for_post(ctx) -> bool:
    """Use the stored post to load its blog without fetching the post again."""
    post = ctx.pstore["post"]
    query_counts["blogs"] += 1
    blog = BLOGS.get(post["blog_id"])
    if blog is None:
        return False

    ctx.pstore["blog"] = blog
    return True


def owns_post(ctx) -> bool:
    post = ctx.pstore["post"]
    return post["author_id"] == current_user_id()


def manages_blog(ctx) -> bool:
    post = ctx.pstore["post"]
    blog = ctx.pstore["blog"]
    return blog["owner_id"] == current_user_id() and post["blog_id"] == blog["id"]


@app.patch("/posts/<int:post_id>")
@rpbac.required(
    All(
        Predicate(load_post),
        Predicate(owns_post),
    )
)
def edit_owned_post(post_id: int):
    return jsonify({"message": "Allowed", "queries": dict(query_counts)})


@app.post("/blogs/posts/<int:post_id>")
@rpbac.required(
    All(
        Predicate(load_post),
        Predicate(load_blog_for_post),
        Predicate(manages_blog),
    )
)
def manage_blog_post(post_id: int):
    return jsonify({"message": "Allowed", "queries": dict(query_counts)})


async def load_post_async(ctx) -> bool:
    """The same sharing pattern works for asynchronous predicate lookups."""
    await asyncio.sleep(0)
    query_counts["posts"] += 1
    post = POSTS.get(ctx.kwargs["post_id"])
    if post is None:
        return False

    ctx.pstore["post"] = post
    return True


async def owns_post_async(ctx) -> bool:
    await asyncio.sleep(0)
    post = ctx.pstore["post"]
    return post["author_id"] == current_user_id()


@app.get("/async-posts/<int:post_id>")
@rpbac.required(All(Predicate(load_post_async), Predicate(owns_post_async)))
async def get_owned_post(post_id: int):
    return jsonify({"post": POSTS[post_id], "queries": dict(query_counts)})


@app.get("/admin-posts/<int:post_id>")
@rpbac.required(
    Any(
        Role("admin"),
        All(Predicate(load_post), Predicate(owns_post)),
    )
)
def get_post_with_admin_or_owner(post_id: int):
    return jsonify({"post": POSTS[post_id], "queries": dict(query_counts)})


if __name__ == "__main__":
    app.run(debug=True)
