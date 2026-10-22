"""
Fingerprint-queue router response models (split from fingerprint_queue.py,
#5832).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pydantic import BaseModel, Field


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
