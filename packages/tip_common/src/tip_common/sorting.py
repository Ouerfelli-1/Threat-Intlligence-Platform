"""Shared sort-by/sort-dir resolver for list endpoints.

Each list endpoint declares a whitelist of columns the client may sort by
(mapping API name -> SQLAlchemy column) and a default. The resolver returns
the appropriate ORDER BY clause, defaulting safely when the client passes
nothing or something invalid.

Why a whitelist:
- prevents SQL injection / `?sort=password_hash` style probing
- gives the client a small stable API even if the underlying schema shifts

Example:
    SORT_COLS = {
        "fetched_at": Article.fetched_at,
        "published_at": Article.published_at,
        "title": Article.title,
        "confidence_score": Article.confidence_score,
        "analyst_status": Article.analyst_status,
    }

    @router.get(...)
    async def list_articles(
        sort_by: str | None = Query(None),
        sort_dir: str | None = Query(None),
        ...
    ):
        stmt = stmt.order_by(resolve_sort(sort_by, sort_dir, SORT_COLS, default="fetched_at"))
"""
from __future__ import annotations

from typing import Any


def resolve_sort(
    sort_by: str | None,
    sort_dir: str | None,
    columns: dict[str, Any],
    *,
    default: str,
    default_dir: str = "desc",
):
    """Pick a SQLAlchemy column + direction with safe fallbacks.

    Args:
        sort_by:    column name from the client (None / unknown -> default)
        sort_dir:   'asc' | 'desc' (None / anything else -> default_dir)
        columns:    whitelist {client_name: sqlalchemy_column}
        default:    fallback column name (must be a key of `columns`)
        default_dir: fallback direction
    """
    key = sort_by if sort_by in columns else default
    col = columns[key]
    direction = (sort_dir or "").lower()
    if direction not in ("asc", "desc"):
        direction = default_dir
    if direction == "desc":
        # nullslast() so NULL `last_modified_at` etc. don't float to the top
        try:
            return col.desc().nullslast()
        except AttributeError:
            return col.desc()
    try:
        return col.asc().nullslast()
    except AttributeError:
        return col.asc()
