# -*- coding: utf-8 -*-

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
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Deque, Dict, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class QueueStats:
    """Statistics for the fingerprint queue."""
    queued: int = 0
    processing: Optional[int] = None
    completed: int = 0
    failed: int = 0
    started_at: Optional[datetime] = None


@dataclass
class FingerprintQueueState:
    """Internal state for the fingerprint queue."""
    queue: Deque[int] = field(default_factory=deque)
    queued_set: Set[int] = field(default_factory=set)  # For O(1) dedup lookup
    processing: Optional[int] = None
    completed: int = 0
    failed: int = 0
    started_at: Optional[datetime] = None


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

    def __init__(
        self,
        fingerprint_generator: Any,
        get_track_filepath: Callable[[int], Optional[str]],
    ) -> None:
        """
        Initialize fingerprint queue.

        Args:
            fingerprint_generator: FingerprintGenerator instance for actual generation
            get_track_filepath: Callable that returns filepath for a track ID (or None)
        """
        self._generator = fingerprint_generator
        self._get_filepath = get_track_filepath
        self._state = FingerprintQueueState()
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._shutdown = False
        self._lock = asyncio.Lock()

    def enqueue(self, track_id: int) -> bool:
        """
        Add a track to the fingerprint queue.

        Thread-safe. Deduplicates (same track won't be queued twice).

        Args:
            track_id: ID of the track to fingerprint

        Returns:
            True if added to queue, False if already queued/processing
        """
        # Check if already queued or currently processing
        if track_id in self._state.queued_set:
            logger.debug(f"Track {track_id} already in fingerprint queue, skipping")
            return False

        if track_id == self._state.processing:
            logger.debug(f"Track {track_id} currently being fingerprinted, skipping")
            return False

        # Add to queue
        self._state.queue.append(track_id)
        self._state.queued_set.add(track_id)
        logger.info(f"📋 Added track {track_id} to fingerprint queue (queue size: {len(self._state.queue)})")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current queue statistics.

        Returns:
            Dict with queue stats (queued, processing, completed, failed)
        """
        return {
            "queued": len(self._state.queue),
            "processing": self._state.processing,
            "completed": self._state.completed,
            "failed": self._state.failed,
            "started_at": self._state.started_at.isoformat() if self._state.started_at else None,
            "is_running": self._worker_task is not None and not self._worker_task.done(),
        }

    def is_queued(self, track_id: int) -> bool:
        """Check if a track is currently queued or being processed."""
        return track_id in self._state.queued_set or track_id == self._state.processing

    async def start(self) -> None:
        """Start the background worker task."""
        if self._worker_task is not None and not self._worker_task.done():
            logger.debug("Fingerprint queue worker already running")
            return

        self._shutdown = False
        self._state.started_at = datetime.now()
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("🚀 Fingerprint queue background worker started")

    async def stop(self) -> None:
        """Stop the background worker gracefully."""
        self._shutdown = True
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        logger.info("🛑 Fingerprint queue background worker stopped")

    async def _worker_loop(self) -> None:
        """
        Background worker loop that processes queued tracks.

        Runs continuously, processing one track at a time.
        Sleeps when queue is empty.
        """
        logger.info("🔄 Fingerprint queue worker loop starting")

        while not self._shutdown:
            try:
                # Check if queue has items
                if not self._state.queue:
                    # Sleep briefly and check again
                    await asyncio.sleep(0.5)
                    continue

                # Get next track from queue
                async with self._lock:
                    if not self._state.queue:
                        continue
                    track_id = self._state.queue.popleft()
                    self._state.queued_set.discard(track_id)
                    self._state.processing = track_id

                logger.info(f"🎵 Processing fingerprint for track {track_id} (remaining: {len(self._state.queue)})")

                # Get filepath for track
                filepath = self._get_filepath(track_id)
                if filepath is None:
                    logger.warning(f"⚠️  Track {track_id} not found or no filepath, skipping")
                    self._state.failed += 1
                    self._state.processing = None
                    continue

                # Generate fingerprint
                try:
                    result = await self._generator.get_or_generate(track_id, filepath)
                    if result is not None:
                        self._state.completed += 1
                        logger.info(f"✅ Fingerprint generated for track {track_id}")
                    else:
                        self._state.failed += 1
                        logger.warning(f"⚠️  Fingerprint generation failed for track {track_id}")
                except Exception as e:
                    self._state.failed += 1
                    logger.error(f"❌ Error generating fingerprint for track {track_id}: {e}")

                self._state.processing = None

            except asyncio.CancelledError:
                logger.info("Fingerprint queue worker cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in fingerprint queue worker: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on persistent errors

        logger.info("🔄 Fingerprint queue worker loop ended")


# Global singleton instance (initialized by backend startup)
_fingerprint_queue: Optional[FingerprintQueue] = None


def get_fingerprint_queue() -> Optional[FingerprintQueue]:
    """Get the global fingerprint queue instance."""
    return _fingerprint_queue


def set_fingerprint_queue(queue: FingerprintQueue) -> None:
    """Set the global fingerprint queue instance."""
    global _fingerprint_queue
    _fingerprint_queue = queue
    logger.info("📋 Global fingerprint queue initialized")
