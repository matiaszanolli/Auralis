"""
Shared pagination utilities for routers.

This module consolidates pagination logic that appears across multiple routers,
reducing boilerplate and ensuring consistency.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Annotated, Any, Literal

from fastapi import Query
from schemas.request_bounds import MAX_SQLITE_INT


def compute_has_more(offset: int, item_count: int, total: int) -> bool:
    """
    Whether more items remain beyond the current page.

    The single source of truth for this formula (#4902) — every paginated
    router previously recomputed ``(offset + len(items)) < total`` inline
    (5 call sites across albums.py, artists.py, tracks.py x2, playlists.py),
    with no shared code to keep them in sync. All 5 now call this one
    function directly; each router's response is keyed by its own domain
    name ("albums"/"artists"/"tracks"/"playlists"), not a generic "items"
    field, so a shared generic response *model* (deleted here — #5054,
    residual scope of #4902 — see ``artists.py::ArtistsListResponse`` for
    the per-router-model pattern the other 4 endpoints should eventually
    adopt) would have been a breaking frontend contract change, not a
    refactor.

    Using ``item_count`` (the actual page length) rather than ``limit``
    handles partial last pages correctly.
    """
    return (offset + item_count) < total


class PaginationParams:
    """
    Standard pagination parameters with validation.

    This provides a consistent way to handle pagination query parameters
    across all endpoints.

    Attributes:
        limit: Maximum number of items to return (1-200, default 50)
        offset: Number of items to skip (0+, default 0)

    Example:
        ```python
        @router.get("/api/artists")
        async def get_artists(
            limit: int = limit_query(),
            offset: int = offset_query(),
        ):
            # Use limit and offset directly
            artists, total = repos.artists.get_all(limit=limit, offset=offset)
        ```
    """
    DEFAULT_LIMIT = 50
    MAX_LIMIT = 200
    MIN_LIMIT = 1
    DEFAULT_OFFSET = 0
    MIN_OFFSET = 0
    MAX_OFFSET = MAX_SQLITE_INT  # a larger value cannot be bound by SQLite (#6162)


def limit_query(description: str | None = None) -> Any:
    """The standard ``limit`` Query parameter (#6222).

    Every paginated handler spelled ``Query(PaginationParams.DEFAULT_LIMIT,
    ge=..., le=...)`` inline — five copies across four routers — so changing
    a bound was a five-file edit. Pass an endpoint-specific ``description``
    where the OpenAPI docs want one; the bounds are identical everywhere.
    """
    if description is not None:
        return Query(
            PaginationParams.DEFAULT_LIMIT,
            ge=PaginationParams.MIN_LIMIT,
            le=PaginationParams.MAX_LIMIT,
            description=description,
        )
    return Query(
        PaginationParams.DEFAULT_LIMIT,
        ge=PaginationParams.MIN_LIMIT,
        le=PaginationParams.MAX_LIMIT,
    )


def offset_query(description: str | None = None) -> Any:
    """The standard ``offset`` Query parameter; see :func:`limit_query`."""
    if description is not None:
        return Query(
            PaginationParams.DEFAULT_OFFSET,
            ge=PaginationParams.MIN_OFFSET,
            le=PaginationParams.MAX_OFFSET,
            description=description,
        )
    return Query(
        PaginationParams.DEFAULT_OFFSET,
        ge=PaginationParams.MIN_OFFSET,
        le=PaginationParams.MAX_OFFSET,
    )


# The ``order`` Query parameter of the album/artist/track lists (#5868).
# ``order_by`` alone could only ascend, so "newest first" was impossible and
# the frontend re-sorted whatever pages it had loaded. Omitted (None), each
# field keeps its natural direction (A-Z, oldest first; artist counts
# most-first). Annotated rather than a ``Query()`` default so a handler called
# directly (the #4670 seam) still receives a plain None.
SortOrder = Annotated[
    Literal['asc', 'desc'] | None,
    Query(description="Sort direction for order_by: asc or desc"),
]


def paginated(key: str, items: Any, total: int, offset: int, limit: int) -> dict[str, Any]:
    """Build the ``{<key>: items, total, offset, limit, has_more}`` envelope.

    One spelling of the page envelope so the key order cannot drift between
    endpoints again (#6222 — the two tracks handlers already disagreed).
    ``has_more`` comes from :func:`compute_has_more` with the actual page
    length, handling partial last pages.
    """
    item_count = len(items) if hasattr(items, "__len__") else 0
    return {
        key: items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": compute_has_more(offset, item_count, total),
    }
