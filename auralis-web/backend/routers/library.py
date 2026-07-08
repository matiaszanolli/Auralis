"""
Library Router
~~~~~~~~~~~~~~

General library endpoints: statistics, reference cloud, browse (artists/albums),
and admin (reset). Track, scan, and fingerprint domains are in dedicated routers:
- routers/tracks.py             (track listing, favorites, lyrics)
- routers/library_scan.py       (directory scan with progress broadcast)
- routers/fingerprint_status.py (fingerprint status and per-track lookup)

Endpoints:
- POST /api/library/refresh-references   - Rebuild mastering reference cloud
- GET  /api/library/stats                - Library statistics
- GET  /api/library/artists              - Paginated artist list
- GET  /api/library/artists/{artist_id}  - Artist detail
- GET  /api/library/albums/{album_id}    - Album detail
- POST /api/library/reset                - Destructive full library reset

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any, cast
from collections.abc import Callable

from fastapi import APIRouter, Header, HTTPException, Query

from .dependencies import require_repository_factory, with_error_handling
from .errors import NotFoundError
from .serializers import serialize_album, serialize_artist, serialize_artists

logger = logging.getLogger(__name__)
router = APIRouter(tags=["library"])


def create_library_router(
    get_repository_factory: Callable[[], Any],
    resolve_worker: Callable[[str], Any] | None = None,
    get_library_manager: Callable[[], Any] | None = None,
) -> APIRouter:
    """Factory: general library routes (stats, browse, reset).

    Args:
        get_repository_factory: Returns the RepositoryFactory.
        resolve_worker: ``resolve_worker(key)`` returns a background-worker
            instance (or ``None``) by component-registry key. Used by the
            destructive reset endpoint to pause/restart all background workers
            so nothing inserts rows mid-reset (#4111).
        get_library_manager: Returns the LibraryManager (for query-cache
            invalidation after a reset, #3770).

    Note:
        Phase 6B: Fully migrated to RepositoryFactory pattern.
        Track / scan / fingerprint routes are registered by their own factory functions
        (create_tracks_router, create_library_scan_router, create_fingerprint_status_router).
    """

    @router.post("/api/library/refresh-references")
    @with_error_handling("refresh reference cloud")
    async def refresh_reference_cloud() -> dict[str, Any]:
        """#3479: rebuild the mastering reference cloud from current library state.

        Clears all existing ``is_reference`` flags, scores every fingerprint
        against the seeder thresholds, and flags the top-N candidates.
        Safe to call repeatedly — the seeder is idempotent and does no audio I/O.
        """
        from auralis.learning.reference_seeder import refresh_cloud
        factory = require_repository_factory(get_repository_factory)
        cleared, selected = await asyncio.to_thread(
            refresh_cloud, factory.fingerprints
        )
        logger.info(
            f"🎯 Reference cloud refresh (manual): cleared {cleared}, selected {selected}"
        )
        return {"cleared": cleared, "selected": selected}

    @router.get("/api/library/stats")
    @with_error_handling("get library stats")
    async def get_library_stats() -> dict[str, Any]:
        """Get library statistics (track count, album count, etc.)."""
        factory = require_repository_factory(get_repository_factory)
        stats = await asyncio.to_thread(factory.stats.get_library_stats)
        return cast(dict[str, Any], stats)

    @router.get("/api/library/artists")
    @with_error_handling("get artists")
    async def get_artists(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        search: str | None = None,
        order_by: str = "name",
    ) -> dict[str, Any]:
        """Get paginated list of artists with optional search."""
        repos = require_repository_factory(get_repository_factory)
        limit = min(max(limit, 1), 200)
        offset = max(offset, 0)
        valid_order_by = ["name", "album_count", "track_count"]
        if order_by not in valid_order_by:
            order_by = "name"

        if search:
            artists, total = await asyncio.to_thread(repos.artists.search, search, limit=limit, offset=offset)
        else:
            artists, total = await asyncio.to_thread(repos.artists.get_all, limit=limit, offset=offset, order_by=order_by)

        has_more = (offset + len(artists)) < total
        return {
            "artists": serialize_artists(artists),
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        }

    @router.get("/api/library/artists/{artist_id}")
    @with_error_handling("get artist")
    async def get_artist(artist_id: int) -> dict[str, Any]:
        """Get artist details by ID with albums and tracks."""
        repos = require_repository_factory(get_repository_factory)
        artist = await asyncio.to_thread(repos.artists.get_by_id, artist_id)
        if not artist:
            raise NotFoundError("Artist", artist_id)
        return serialize_artist(artist)

    # Removed: GET /api/library/albums — dead endpoint, duplicate of GET /api/albums (fixes #2509)

    @router.get("/api/library/albums/{album_id}")
    @with_error_handling("get album")
    async def get_album(album_id: int) -> dict[str, Any]:
        """Get album details by ID with tracks."""
        repos = require_repository_factory(get_repository_factory)
        album = await asyncio.to_thread(repos.albums.get_by_id, album_id)
        if not album:
            raise NotFoundError("Album", album_id)
        return serialize_album(album)

    @router.post("/api/library/reset")
    @with_error_handling("reset library")
    async def reset_library(
        x_confirm_reset: str = Header(
            ...,
            alias="X-Confirm-Reset",
            description="Must be 'RESET' to confirm the destructive operation",
        ),
    ) -> dict[str, Any]:
        """Reset the entire library — deletes all tracks, albums, artists, genres,
        fingerprints, playlists, queue state, and play statistics.

        Requires the ``X-Confirm-Reset: RESET`` header as a safety guard
        against accidental or CSRF-triggered calls.
        """
        if x_confirm_reset != "RESET":
            raise HTTPException(
                status_code=400,
                detail="Invalid confirmation header: X-Confirm-Reset must be 'RESET'",
            )
        repos = require_repository_factory(get_repository_factory)

        from config.background_workers import (
            start_background_workers,
            stop_background_workers,
        )

        # Pause every background worker (auto_scanner, ondemand + batch
        # fingerprint queues) so none can insert Track/TrackFingerprint rows
        # between the deletes and commit, which would make the reset
        # non-atomic (fixes #3342, #4111). Previously only the on-demand
        # queue was paused.
        resolve = resolve_worker or (lambda _key: None)
        stopped = await stop_background_workers(resolve)
        try:
            # Bulk delete runs in the repository layer (no raw session in the
            # router) and off the event loop.
            await asyncio.to_thread(repos.reset_library)

            # Drop the LibraryManager query cache so reads don't return
            # pre-reset data (#3770).
            if get_library_manager is not None:
                library_manager = get_library_manager()
                if library_manager is not None and hasattr(library_manager, "clear_cache"):
                    library_manager.clear_cache()

            logger.info(
                "Library reset: all tracks, albums, artists, genres, "
                "fingerprints, and playlists deleted"
            )
        finally:
            # Always restart the workers we paused, even if the reset failed.
            await start_background_workers(resolve, stopped)

        return {"message": "Library has been reset successfully"}

    return router
