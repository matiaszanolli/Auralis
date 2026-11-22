"""
Fingerprint Queue - Background Fingerprint Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Manages a background queue for fingerprint generation. When a fingerprint
is requested but not found (404), the track is added to the queue and
processed asynchronously in the background.

Features:
- In-memory FIFO queue for track IDs
- Single background worker (one fingerprint at a time)
- Deduplication (same track won't be queued twice)
- Status tracking (queue length, currently processing, completed)
- Graceful shutdown support

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Callable, Iterable
from typing import Any, Literal

from helpers import spawn_background_task

from .fingerprint_queue_state import FingerprintQueueState

logger = logging.getLogger(__name__)
_IDLE_POLL_S = 0.5  # no track to fingerprint: look again after this (#6642)
_ERROR_BACKOFF_S = 1.0  # after an unexpected worker error


class FingerprintQueue:
    """
    Background queue for fingerprint generation.

    Manages a queue of track IDs that need fingerprints generated.
    A single background worker processes tracks one at a time.

    Usage:
        queue = FingerprintQueue(fingerprint_generator, get_track_filepath)
        await queue.start()

        # When fingerprint not found:
        queue.enqueue(track_id)

        # Check status:
        stats = queue.get_stats()

        # Shutdown:
        await queue.stop()
    """

    MAX_QUEUE_SIZE = 5000

    def __init__(
        self,
        fingerprint_generator: Any,
        get_track_filepath: Callable[[int], str | None],
    ) -> None:
        """
        Initialize fingerprint queue.

        Args:
            fingerprint_generator: FingerprintGenerator instance for actual generation
            get_track_filepath: Callable that returns filepath for a track ID (or None)
        """
        self._generator = fingerprint_generator
        self._get_filepath = get_track_filepath
        # Thread-safe on its own lock: enqueue() runs through asyncio.to_thread (#5261).
        self._state = FingerprintQueueState()
        self._worker_task: asyncio.Task[None] | None = None
        self._shutdown = False

    def enqueue(self, track_id: int) -> bool:
        """
        Add a track to the fingerprint queue.

        Thread-safe: the check-then-mutate runs under the state lock the
        background worker's dequeue also takes. Deduplicates (same track won't
        be queued twice).

        Args:
            track_id: ID of the track to fingerprint

        Returns:
            True if added to queue, False if already queued/processing or the queue is full
        """
        outcome, queue_size = self._state.add(track_id, self.MAX_QUEUE_SIZE)
        if outcome == "queued":
            logger.debug(f"Track {track_id} already in fingerprint queue, skipping")
        elif outcome == "processing":
            logger.debug(f"Track {track_id} currently being fingerprinted, skipping")
        elif outcome == "full":
            logger.warning(
                f"Fingerprint queue full ({self.MAX_QUEUE_SIZE} entries); "
                f"dropping track {track_id}. The worker will process queued tracks first."
            )
        else:
            logger.info(f"📋 Added track {track_id} to fingerprint queue (queue size: {queue_size})")
        return outcome == "added"

    def enqueue_many(self, track_ids: Iterable[int]) -> tuple[int, int, int]:
        """Enqueue each track; returns (enqueued, already_pending, dropped_queue_full) (#5920).

        enqueue() answers False for a duplicate and for a full queue alike, so a rejected
        track that is not pending is a queue-full drop.
        """
        enqueued = already_pending = dropped = 0
        for track_id in track_ids:
            if self.enqueue(track_id):
                enqueued += 1
            elif self.is_pending(track_id):
                already_pending += 1
            else:
                dropped += 1
        return enqueued, already_pending, dropped

    def is_pending(self, track_id: int) -> bool:
        """True when the track is waiting in the queue or being fingerprinted right now."""
        return self._state.is_pending(track_id)

    def get_stats(self) -> dict[str, Any]:
        """
        Get current queue statistics.

        Returns:
            Dict with queue stats (queued, processing, completed, failed)
        """
        stats = self._state.snapshot()
        return {
            **stats,
            "is_running": self._worker_task is not None and not self._worker_task.done(),
        }

    async def start(self) -> None:
        """Start the background worker task."""
        if self._worker_task is not None and not self._worker_task.done():
            logger.debug("Fingerprint queue worker already running")
            return

        self._shutdown = False
        self._state.mark_started()
        self._worker_task = spawn_background_task(self._worker_loop(), name="fingerprint_queue._worker_loop")
        logger.info("🚀 Fingerprint queue background worker started")

    async def stop(self) -> None:
        """Stop the background worker gracefully.

        Also drops everything pending (#6094). Stopping is how the library
        reset pauses this queue, and track ids restart from 1 on a fresh
        library, so a queued or in-flight id from before the reset would
        otherwise be fingerprinted (or refused as "already processing") against
        a different track after ``start()``.
        """
        self._shutdown = True
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        self._state.drop_pending()
        logger.info("🛑 Fingerprint queue background worker stopped")

    async def _generate_one(self, track_id: int, filepath: str) -> Literal["completed", "failed"]:
        """Generate one fingerprint; returns how it ended for the state counters."""
        try:
            result = await self._generator.get_or_generate(track_id, filepath)
        except Exception as e:
            logger.error(f"❌ Error generating fingerprint for track {track_id}: {e}")
            return "failed"

        if result is None:
            logger.warning(f"⚠️  Fingerprint generation failed for track {track_id}")
            return "failed"
        logger.info(f"✅ Fingerprint generated for track {track_id}")
        return "completed"

    async def _process(self, track_id: int, remaining: int) -> None:
        """Look up the track's file and fingerprint it, then release it from processing."""
        logger.info(f"🎵 Processing fingerprint for track {track_id} (remaining: {remaining})")
        # A synchronous repository query: off the event loop, which also
        # carries WS control traffic (#5390).
        filepath = await asyncio.to_thread(self._get_filepath, track_id)
        if filepath is None:
            logger.warning(f"⚠️  Track {track_id} not found or no filepath, skipping")
            self._state.finish("failed")
            return
        self._state.finish(await self._generate_one(track_id, filepath))

    async def _worker_loop(self) -> None:
        """Process queued tracks one at a time until stopped; idles briefly when empty."""
        logger.info("🔄 Fingerprint queue worker loop starting")

        while not self._shutdown:
            try:
                track_id, remaining = self._state.pop_next()
                if track_id is None:
                    await asyncio.sleep(_IDLE_POLL_S)
                    continue
                await self._process(track_id, remaining)
            except asyncio.CancelledError:
                logger.info("Fingerprint queue worker cancelled")
                self._state.finish("cancelled")  # the cancelled track is no longer in flight
                break
            except Exception as e:
                logger.error(f"Unexpected error in fingerprint queue worker: {e}")
                await asyncio.sleep(_ERROR_BACKOFF_S)  # no tight loop on a persistent error

        logger.info("🔄 Fingerprint queue worker loop ended")


# Global singleton instance (initialized by backend startup)
_fingerprint_queue: FingerprintQueue | None = None


def get_fingerprint_queue() -> FingerprintQueue | None:
    """Get the global fingerprint queue instance."""
    return _fingerprint_queue


def set_fingerprint_queue(queue: FingerprintQueue | None) -> None:
    """Set (or clear, with None) the global fingerprint queue instance.

    Called with None on rollback/shutdown (#4803) so get_fingerprint_queue()
    correctly reports unavailable instead of returning a stopped queue object
    that all 8 real consumers would otherwise keep enqueueing dead work into.
    """
    global _fingerprint_queue
    _fingerprint_queue = queue
    if queue is not None:
        logger.info("📋 Global fingerprint queue initialized")
    else:
        logger.info("📋 Global fingerprint queue cleared")
