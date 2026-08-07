"""
Shared pagination utilities for routers.

This module consolidates pagination logic that appears across multiple routers,
reducing boilerplate and ensuring consistency.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations


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
            limit: int = Query(50, ge=1, le=200),
            offset: int = Query(0, ge=0)
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
