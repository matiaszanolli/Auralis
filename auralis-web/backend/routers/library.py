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
- POST /api/library/reset                - Destructive full library reset

Artist and album browse/detail endpoints live in the dedicated routers/artists.py
and routers/albums.py (fixes #3824 / BE-RH-7 — /api/library/artists,
/api/library/artists/{id}, and /api/library/albums/{id} were dead-end
duplicates of /api/artists, /api/artists/{id}, and /api/albums/{id} with a
different, undocumented response shape; the frontend never called them, per
useLibraryQuery.ts's own comment and its test asserting the library.py URLs
are never used).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from core.cache_cleanup import clear_all_caches
from core.thumbnail_cache import artwork_cache_root
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .dependencies import require_repository_factory, with_error_handling

logger = logging.getLogger(__name__)


class RefreshReferencesResponse(BaseModel):
    """Result of rebuilding the mastering reference cloud (#3479)."""
    cleared: int = Field(description="Existing is_reference flags cleared")
    selected: int = Field(description="Fingerprints newly flagged as references")


class LibraryStatsResponse(BaseModel):
    """Library-wide statistics (`StatsRepository.get_library_stats`).

    `avg_dr_rating` / `avg_lufs` are deliberate duplicates of
    `average_dr` / `average_lufs` — the repository emits both because the
    frontend reads the former pair. Declaring only one of each would delete
    the other from the response.

    Every counter carries a default even though the repository always
    populates all of them. A `response_model` validates as well as filters, so
    required fields would turn any partial payload — a stub repository, a
    future query that stops computing one aggregate — into a 500 with an empty
    body. Defaulting degrades to zero instead, matching the
    `_safe_collection`/`_safe_scalar` posture the ORM layer already takes, and
    the OpenAPI schema is equally complete either way.
    """
    total_tracks: int = Field(default=0, description="Number of tracks")
    total_albums: int = Field(default=0, description="Number of albums")
    total_artists: int = Field(default=0, description="Number of artists")
    total_genres: int = Field(default=0, description="Number of genres")
    total_playlists: int = Field(default=0, description="Number of playlists")
    total_duration: float = Field(default=0.0, description="Summed track duration in seconds")
    total_duration_formatted: str = Field(default="", description="Human-readable total duration")
    total_filesize: int = Field(default=0, description="Summed file size in bytes")
    total_filesize_gb: float = Field(default=0.0, description="Summed file size in GB (2 dp)")
    total_plays: int = Field(default=0, description="Summed play count")
    favorite_count: int = Field(default=0, description="Number of favorited tracks")
    average_dr: float | None = Field(default=None, description="Mean dynamic-range rating")
    average_lufs: float | None = Field(default=None, description="Mean integrated loudness")
    avg_dr_rating: float | None = Field(default=None, description="Alias of average_dr")
    avg_lufs: float | None = Field(default=None, description="Alias of average_lufs")


class LibraryResetResponse(BaseModel):
    """Confirmation returned by the destructive library reset."""
    message: str = Field(description="Human-readable confirmation")


def create_library_router(
    get_repository_factory: Callable[[], Any],
    resolve_worker: Callable[[str], Any] | None = None,
    get_cache_manager: Callable[[], Any] | None = None,
    get_artwork_cache_dir: Callable[[], Path] = artwork_cache_root,
) -> APIRouter:
    """Factory: general library routes (stats, browse, reset).

    Args:
        get_repository_factory: Returns the RepositoryFactory.
        resolve_worker: ``resolve_worker(key)`` returns a background-worker
            instance (or ``None``) by component-registry key. Used by the
            destructive reset endpoint to pause/restart all background workers
            so nothing inserts rows mid-reset (#4111).
        get_cache_manager: Returns the shared chunk cache when initialized.
        get_artwork_cache_dir: Returns the source-artwork cache root.

    Note:
        Phase 6B: Fully migrated to RepositoryFactory pattern.
        Track / scan / fingerprint routes are registered by their own factory functions
        (create_tracks_router, create_library_scan_router, create_fingerprint_status_router).
    """
    # Fresh router per factory call (#4361) — a module-level router shared
    # across calls means a second factory call (e.g. in tests) re-registers
    # or shadows routes on the same object, and any dependency override bound
    # on that second call silently never takes effect (FastAPI serves the
    # first-registered handler). Matches the isolated-per-factory pattern
    # metadata.py:87 documents.
    router = APIRouter(tags=["library"])

    @router.post("/api/library/refresh-references", response_model=RefreshReferencesResponse)
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

    @router.get("/api/library/stats", response_model=LibraryStatsResponse)
    @with_error_handling("get library stats")
    async def get_library_stats() -> dict[str, Any]:
        """Get library statistics (track count, album count, etc.)."""
        factory = require_repository_factory(get_repository_factory)
        stats = await asyncio.to_thread(factory.stats.get_library_stats)
        return cast(dict[str, Any], stats)

    @router.post("/api/library/reset", response_model=LibraryResetResponse)
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

            # One lifecycle boundary owns every backend cache tier (#5257).
            # Run it while workers remain paused so a rescan cannot repopulate
            # stale entries between the database reset and cache cleanup.
            cache_manager = get_cache_manager() if get_cache_manager else None
            await clear_all_caches(
                cache_manager,
                get_artwork_cache_dir(),
                clear_source_artwork=True,
            )

            # #4619 / #3770: no query cache to drop any more. The
            # `@cached_query` decorators live only on the deprecated
            # LibraryManager facade, which the backend no longer constructs —
            # every read here goes through the repositories, straight to
            # SQLite, so a reset cannot leave stale rows behind a cache.
            logger.info(
                "Library reset: all tracks, albums, artists, genres, "
                "fingerprints, and playlists deleted"
            )
        finally:
            # Always restart the workers we paused, even if the reset failed.
            await start_background_workers(resolve, stopped)

        return {"message": "Library has been reset successfully"}

    return router
