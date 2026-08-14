"""
Fingerprint Queue API Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

REST API endpoints for the on-demand fingerprint-generation queue and overall
fingerprint statistics. Split out of similarity.py (#4270); all routes keep
their original ``/api/similarity/fingerprint-queue*`` and
``/api/similarity/fingerprint-stats`` paths.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import uuid
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .errors import NotFoundError
from .dependencies import require_repository_factory
from .similarity_common import _with_similarity_error_handling

logger = logging.getLogger(__name__)


class FingerprintQueueStatusResponse(BaseModel):
    """On-demand fingerprint queue status.

    Every field but `available` is optional because this route reports
    failures as a 200-OK body rather than an HTTPException: an uninitialized
    queue returns `{available: False, message}` and an internal error returns
    `{available: False, error, ref}`, neither of which carries queue counters.
    """
    available: bool = Field(description="False when the queue is absent or errored")
    queued: int | None = Field(default=None, description="Tracks waiting in the queue")
    processing: int | None = Field(default=None, description="Track ID being processed, if any")
    completed: int | None = Field(default=None, description="Fingerprints generated")
    failed: int | None = Field(default=None, description="Failed generation attempts")
    started_at: str | None = Field(default=None, description="Worker start time (ISO 8601)")
    is_running: bool | None = Field(default=None, description="True while the worker is active")
    message: str | None = Field(default=None, description="Explanation when unavailable")
    error: str | None = Field(default=None, description="Error code when the read failed")
    ref: str | None = Field(default=None, description="Correlation id for the server-side log (#3331)")


class EnqueueFingerprintResponse(BaseModel):
    """Result of enqueueing one track for fingerprinting.

    `track_id` is absent on the already-fingerprinted early return, which
    exits before the queue is consulted.
    """
    enqueued: bool = Field(description="True when the track was added to the queue")
    track_id: int | None = Field(default=None, description="Track that was enqueued")
    reason: str = Field(description="Why the track was or was not enqueued")


class EnqueueAllFingerprintsResponse(BaseModel):
    """Result of a batch enqueue of every track missing a fingerprint.

    `skipped` / `pending_after` are absent on the nothing-to-do early return.
    """
    enqueued: int = Field(description="Tracks added to the queue")
    skipped: int | None = Field(default=None, description="Tracks already queued or processing")
    already_fingerprinted: int = Field(description="Tracks that already had a fingerprint")
    total_tracks: int = Field(description="Total tracks in the library")
    pending_after: int | None = Field(default=None, description="Tracks still missing a fingerprint")
    message: str = Field(description="Human-readable summary")


class FingerprintStatsResponse(BaseModel):
    """Library-wide fingerprint coverage."""
    total_tracks: int = Field(description="Total tracks in the library")
    fingerprinted: int = Field(description="Tracks with a fingerprint")
    pending: int = Field(description="Tracks still missing a fingerprint")
    progress_percent: float = Field(description="Coverage percentage (0–100)")
    message: str = Field(description="Human-readable summary")


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
    router = APIRouter(prefix="/api/similarity", tags=["fingerprint-queue"])

    @router.get("/fingerprint-queue/status", response_model=FingerprintQueueStatusResponse)
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

    @router.post("/fingerprint-queue/enqueue/{track_id}", response_model=EnqueueFingerprintResponse)
    @_with_similarity_error_handling("Error enqueueing track")
    async def enqueue_fingerprint(track_id: int) -> dict[str, Any]:
        """
        Manually enqueue a track for fingerprint generation.

        Args:
            track_id: ID of the track to fingerprint

        Returns:
            Status of the enqueue operation
        """
        repos = require_repository_factory(get_repository_factory)

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

        if queue is None:
            raise HTTPException(
                status_code=503,
                detail="On-demand fingerprint queue not available"
            )

        added = await asyncio.to_thread(queue.enqueue, track_id)
        return {
            "enqueued": added,
            "track_id": track_id,
            "reason": "Added to queue" if added else "Already queued or processing"
        }

    @router.post("/fingerprint-queue/enqueue-all", response_model=EnqueueAllFingerprintsResponse)
    @_with_similarity_error_handling("Error batch enqueueing tracks")
    async def enqueue_all_missing_fingerprints(
        limit: int | None = Query(None, ge=1, le=10000, description="Maximum tracks to enqueue (default: all)")
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
        repos = require_repository_factory(get_repository_factory)

        # Get fingerprint stats
        stats = await asyncio.to_thread(repos.fingerprints.get_fingerprint_stats)
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

        if queue is None:
            raise HTTPException(
                status_code=503,
                detail="On-demand fingerprint queue not available"
            )

        # Get tracks without fingerprints
        missing_tracks = await asyncio.to_thread(repos.fingerprints.get_missing_fingerprints, limit=limit)

        # Enqueue each track (offloaded to thread to avoid blocking
        # the event loop for large libraries — #3335)
        def _enqueue_batch() -> tuple[int, int]:
            enqueued = 0
            skipped = 0
            for track in missing_tracks:
                if queue.enqueue(track.id):
                    enqueued += 1
                else:
                    skipped += 1
            return enqueued, skipped

        enqueued_count, skipped_count = await asyncio.to_thread(_enqueue_batch)

        logger.info(f"📋 Batch enqueued {enqueued_count} tracks for fingerprinting ({skipped_count} skipped)")

        return {
            "enqueued": enqueued_count,
            "skipped": skipped_count,
            "already_fingerprinted": already_fingerprinted,
            "total_tracks": total_tracks,
            "pending_after": pending - enqueued_count,
            "message": f"Enqueued {enqueued_count} tracks for background fingerprinting"
        }

    @router.get("/fingerprint-stats", response_model=FingerprintStatsResponse)
    @_with_similarity_error_handling("Error getting fingerprint stats")
    async def get_fingerprint_stats() -> dict[str, Any]:
        """
        Get overall fingerprint statistics for the library.

        Returns:
            Statistics including total tracks, fingerprinted count, and progress
        """
        repos = require_repository_factory(get_repository_factory)
        stats = await asyncio.to_thread(repos.fingerprints.get_fingerprint_stats)

        return {
            "total_tracks": stats['total'],
            "fingerprinted": stats['fingerprinted'],
            "pending": stats['pending'],
            "progress_percent": stats['progress_percent'],
            "message": f"{stats['fingerprinted']}/{stats['total']} tracks fingerprinted ({stats['progress_percent']}%)"
        }

    return router
