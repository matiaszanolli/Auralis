"""
Fingerprint Queue API Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

REST API endpoints for the on-demand fingerprint-generation queue and overall
fingerprint statistics. Split out of similarity.py (#4270); all routes keep
their original ``/api/similarity/fingerprint-queue*`` and
``/api/similarity/fingerprint-stats`` paths.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import uuid
from typing import Annotated, Any
from collections.abc import Callable

from fastapi import APIRouter, Depends, Path, Query

from .errors import NotFoundError
from .dependencies import require_service
from .repo_deps import RepositoryFactoryDeps
from .fingerprint_queue_models import (  # noqa: F401
    EnqueueAllFingerprintsResponse,
    EnqueueFingerprintResponse,
    FingerprintQueueStatusResponse,
    FingerprintStatsResponse,
)
from .similarity_common import _with_similarity_error_handling

logger = logging.getLogger(__name__)

_repo_deps = RepositoryFactoryDeps("fingerprint_queue")


async def get_fingerprint_queue_status() -> dict[str, Any]:
    """
    Get status of the on-demand fingerprint generation queue.

    Returns queue statistics including:
    - queued: Number of tracks waiting in queue
    - processing: Track ID currently being processed (or null)
    - completed: Number of fingerprints generated
    - failed: Number of failed generation attempts
    - is_running: Whether the background worker is active

    Returns:
        Queue status dictionary

    Note:
        Unlike the other endpoints in this router, errors here are reported
        as a 200-OK body (`available: False`) rather than an HTTPException,
        so this endpoint intentionally keeps its own try/except rather than
        using `_with_similarity_error_handling` (which always re-raises).
    """
    try:
        from analysis.fingerprint_queue import get_fingerprint_queue
        queue = get_fingerprint_queue()

        if queue is None:
            return {
                "available": False,
                "message": "On-demand fingerprint queue not initialized"
            }

        stats = await asyncio.to_thread(queue.get_stats)
        stats["available"] = True
        return stats

    except Exception as e:
        # Same #3331 leak class as the HTTPException paths but via a
        # 200-OK response body: log the full exception server-side,
        # return only a correlation id so callers can report it.
        ref = uuid.uuid4().hex[:8]
        logger.exception("[similarity:%s] Error getting fingerprint queue status", ref, exc_info=e)
        return {
            "available": False,
            "error": "internal_error",
            "ref": ref,
        }


@_with_similarity_error_handling("Error enqueueing track")
async def enqueue_fingerprint(
    track_id: Annotated[int, Path(ge=1)],
    repos: Any = Depends(_repo_deps.get_repos),
) -> dict[str, Any]:
    """
    Manually enqueue a track for fingerprint generation.

    Args:
        track_id: ID of the track to fingerprint

    Returns:
        Status of the enqueue operation
    """
    # Check if track exists
    track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)
    if not track:
        raise NotFoundError("Track", track_id)

    # Check if already has fingerprint
    if await asyncio.to_thread(repos.fingerprints.exists, track_id):
        return {
            "enqueued": False,
            "reason": "Track already has fingerprint"
        }

    # Enqueue
    from analysis.fingerprint_queue import get_fingerprint_queue
    queue = get_fingerprint_queue()

    queue = require_service(queue, "On-demand fingerprint queue")

    added = await asyncio.to_thread(queue.enqueue, track_id)
    return {
        "enqueued": added,
        "track_id": track_id,
        "reason": "Added to queue" if added else "Already queued or processing"
    }


@_with_similarity_error_handling("Error batch enqueueing tracks")
async def enqueue_all_missing_fingerprints(
    limit: int | None = Query(None, ge=1, le=10000, description="Maximum tracks to enqueue (default: all)"),
    repos: Any = Depends(_repo_deps.get_repos),
) -> dict[str, Any]:
    """
    Enqueue all tracks that don't have fingerprints for background processing.

    This scans the database for tracks without fingerprints and adds them
    to the background queue for processing. Fingerprints are generated
    in a separate process to avoid blocking playback.

    Args:
        limit: Maximum number of tracks to enqueue (default: all missing)

    Returns:
        Statistics about the enqueue operation
    """
    # Get fingerprint stats
    stats = await asyncio.to_thread(repos.fingerprint_stats.get_fingerprint_stats)
    total_tracks = stats['total']
    already_fingerprinted = stats['fingerprinted']
    pending = stats['pending']

    if pending == 0:
        return {
            "enqueued": 0,
            "already_fingerprinted": already_fingerprinted,
            "total_tracks": total_tracks,
            "message": "All tracks already have fingerprints!"
        }

    # Get the fingerprint queue
    from analysis.fingerprint_queue import get_fingerprint_queue
    queue = get_fingerprint_queue()

    queue = require_service(queue, "On-demand fingerprint queue")

    # Get tracks without fingerprints
    missing_tracks = await asyncio.to_thread(repos.fingerprints.get_missing_fingerprints, limit=limit)

    # Offloaded so a large batch does not block the event loop (#3335).
    enqueued_count, skipped_count, dropped_count = await asyncio.to_thread(
        queue.enqueue_many, [track.id for track in missing_tracks]
    )

    logger.info(
        f"📋 Batch enqueued {enqueued_count} tracks for fingerprinting "
        f"({skipped_count} already pending, {dropped_count} dropped: queue full)"
    )

    return {
        "enqueued": enqueued_count,
        "skipped": skipped_count,
        "dropped_queue_full": dropped_count,
        "already_fingerprinted": already_fingerprinted,
        "total_tracks": total_tracks,
        "pending_after": pending - enqueued_count,
        "message": f"Enqueued {enqueued_count} tracks for background fingerprinting"
        + (f"; {dropped_count} did not fit in the full queue, run it again once it drains" if dropped_count else ""),
    }


@_with_similarity_error_handling("Error getting fingerprint stats")
async def get_fingerprint_stats(repos: Any = Depends(_repo_deps.get_repos)) -> dict[str, Any]:
    """
    Get overall fingerprint statistics for the library.

    Returns: total tracks, fingerprinted count, and progress.
    """
    stats = await asyncio.to_thread(repos.fingerprint_stats.get_fingerprint_stats)
    fingerprinted = stats.get('current', stats['fingerprinted'])  # usable rows, as progress_percent counts (#5891)
    return {
        "total_tracks": stats['total'],
        "fingerprinted": fingerprinted,
        "pending": max(0, stats['total'] - fingerprinted),
        "progress_percent": stats['progress_percent'],
        "message": f"{fingerprinted}/{stats['total']} tracks fingerprinted ({stats['progress_percent']}%)"
    }


def create_fingerprint_queue_router(
    get_repository_factory: Callable[[], Any]
) -> APIRouter:
    """
    Create the fingerprint-queue admin router with dependency injection

    Args:
        get_repository_factory: Callable that returns RepositoryFactory instance

    Returns:
        Configured FastAPI router
    """
    router = APIRouter(
        prefix="/api/similarity",
        tags=["fingerprint-queue"],
        dependencies=[Depends(_repo_deps.bind(get_repository_factory))],
    )
    router.add_api_route(
        "/fingerprint-queue/status",
        get_fingerprint_queue_status,
        methods=["GET"],
        response_model=FingerprintQueueStatusResponse,
    )
    router.add_api_route(
        "/fingerprint-queue/enqueue/{track_id}",
        enqueue_fingerprint,
        methods=["POST"],
        response_model=EnqueueFingerprintResponse,
    )
    router.add_api_route(
        "/fingerprint-queue/enqueue-all",
        enqueue_all_missing_fingerprints,
        methods=["POST"],
        response_model=EnqueueAllFingerprintsResponse,
    )
    router.add_api_route(
        "/fingerprint-stats",
        get_fingerprint_stats,
        methods=["GET"],
        response_model=FingerprintStatsResponse,
    )
    return router
