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
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from core.cache_cleanup import clear_all_caches
from core.thumbnail_cache import artwork_cache_root
from fastapi import APIRouter, Depends, Header, HTTPException

from .errors import BadRequestError
from .dependencies import require_repository_factory, with_error_handling
from .library_deps import _LibraryDeps, _deps, _get_deps  # noqa: F401
from .library_models import (  # noqa: F401
    LibraryResetResponse,
    LibraryStatsResponse,
    RefreshReferencesResponse,
)

logger = logging.getLogger(__name__)


@with_error_handling("refresh reference cloud")
async def refresh_reference_cloud(
    deps: _LibraryDeps = Depends(_get_deps),
) -> dict[str, Any]:
    """#3479: rebuild the mastering reference cloud from current library state.

    Clears all existing ``is_reference`` flags, scores every fingerprint
    against the seeder thresholds, and flags the top-N candidates.
    Safe to call repeatedly — the seeder is idempotent and does no audio I/O.
    """
    from auralis.learning.reference_seeder import refresh_cloud
    factory = require_repository_factory(deps.get_repository_factory)
    cleared, selected = await asyncio.to_thread(
        refresh_cloud, factory.fingerprints
    )
    logger.info(
        f"🎯 Reference cloud refresh (manual): cleared {cleared}, selected {selected}"
    )
    return {"cleared": cleared, "selected": selected}


@with_error_handling("get library stats")
async def get_library_stats(
    deps: _LibraryDeps = Depends(_get_deps),
) -> dict[str, Any]:
    """Get library statistics (track count, album count, etc.)."""
    factory = require_repository_factory(deps.get_repository_factory)
    stats = await asyncio.to_thread(factory.stats.get_library_stats)
    return cast(dict[str, Any], stats)


@with_error_handling("reset library")
async def reset_library(
    x_confirm_reset: str = Header(
        ...,
        alias="X-Confirm-Reset",
        description="Must be 'RESET' to confirm the destructive operation",
    ),
    deps: _LibraryDeps = Depends(_get_deps),
) -> dict[str, Any]:
    """Reset the entire library — deletes all tracks, albums, artists, genres,
    fingerprints, playlists, queue state, and play statistics.

    Requires the ``X-Confirm-Reset: RESET`` header as a safety guard
    against accidental or CSRF-triggered calls.
    """
    if x_confirm_reset != "RESET":
        raise BadRequestError("Invalid confirmation header: X-Confirm-Reset must be 'RESET'")
    repos = require_repository_factory(deps.get_repository_factory)

    from config.background_workers import (
        start_background_workers,
        stop_background_workers,
        unstopped_workers_detail,
    )

    # Take exclusive access to the library BEFORE pausing anything (#4816).
    # stop_background_workers() only reaches the registered workers; a manual
    # scan (POST /api/library/scan) is a transient LibraryScanner under no
    # registry key, so it used to keep importing files straight through the
    # reset and silently undo it. The scan-slot registry on LibraryDatabase is
    # the one place that knows a scan is running (the counter the scan route's
    # own 409 arbitrates on), so this rejects a reset that races a scan and
    # blocks any scan that would start during one.
    library_database = deps.get_library_database() if deps.get_library_database else None
    exclusive_held = False
    if library_database is not None:
        exclusive_held = library_database.try_begin_exclusive_access()
        if not exclusive_held:
            raise HTTPException(
                status_code=409,
                detail=(
                    "A library scan is in progress. Wait for it to finish "
                    "(or cancel it) before resetting the library."
                ),
            )
    else:
        logger.warning(
            "Library reset proceeding without the scan-slot guard: "
            "library database unavailable (#4816)"
        )

    # Pause every background worker (auto_scanner, ondemand + batch
    # fingerprint queues) so none can insert Track/TrackFingerprint rows
    # between the deletes and commit, which would make the reset
    # non-atomic (#3342, #4111). One that outlives its stop timeout may still
    # be writing, so the reset is refused rather than run under it (#6095).
    resolve = deps.resolve_worker or (lambda _key: None)
    unstopped: list[str] = []
    stopped = await stop_background_workers(resolve, unstopped)
    try:
        if unstopped:
            raise HTTPException(status_code=409, detail=unstopped_workers_detail(unstopped))
        # Bulk delete runs in the repository layer, off the event loop.
        await asyncio.to_thread(repos.reset_library)

        # One lifecycle boundary owns every backend cache tier (#5257), run
        # while workers stay paused so a rescan cannot repopulate stale entries.
        cache_manager = deps.get_cache_manager() if deps.get_cache_manager else None
        await clear_all_caches(
            cache_manager,
            deps.get_artwork_cache_dir(),
            clear_source_artwork=True,
        )

        # No query cache to drop: every read goes straight to SQLite.
        logger.info(
            "Library reset: all tracks, albums, artists, genres, "
            "fingerprints, and playlists deleted"
        )
    finally:
        # Always restart the workers we paused, even if the reset failed.
        await start_background_workers(resolve, stopped)
        # Release exclusive access last, so scans stay blocked until the
        # workers that could feed them are back up (#4816).
        if exclusive_held and library_database is not None:
            library_database.end_exclusive_access()

    return {"message": "Library has been reset successfully"}


def create_library_router(
    get_repository_factory: Callable[[], Any],
    resolve_worker: Callable[[str], Any] | None = None,
    get_cache_manager: Callable[[], Any] | None = None,
    get_artwork_cache_dir: Callable[[], Path] = artwork_cache_root,
    get_library_database: Callable[[], Any] | None = None,
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
        get_library_database: Returns the LibraryDatabase, which owns the
            scan-slot registry. The destructive reset endpoint takes exclusive
            access through it so an in-flight manual scan — a transient
            LibraryScanner that is NOT a registered background worker — cannot
            re-insert rows the reset just deleted (#4816).

    Note:
        Track / scan / fingerprint routes are registered by their own factory functions
        (create_tracks_router, create_library_scan_router, create_fingerprint_status_router).
    """
    # Fresh router per factory call (#4361): a module-level router shared
    # across calls would re-register or shadow routes on the same object. The
    # handlers reach this call's collaborators through RouterDeps (#5832).
    deps = _LibraryDeps(
        get_repository_factory,
        resolve_worker,
        get_cache_manager,
        get_artwork_cache_dir,
        get_library_database,
    )
    router = APIRouter(tags=["library"], dependencies=[Depends(_deps.bind(deps))])
    router.add_api_route(
        "/api/library/refresh-references",
        refresh_reference_cloud,
        methods=["POST"],
        response_model=RefreshReferencesResponse,
    )
    router.add_api_route(
        "/api/library/stats",
        get_library_stats,
        methods=["GET"],
        response_model=LibraryStatsResponse,
    )
    router.add_api_route(
        "/api/library/reset",
        reset_library,
        methods=["POST"],
        response_model=LibraryResetResponse,
    )
    return router
