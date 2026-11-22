"""
Fingerprint Queue State
~~~~~~~~~~~~~~~~~~~~~~~

The pending/processing bookkeeping behind ``FingerprintQueue`` (#6698): the
FIFO, its dedup set, the in-flight track and the outcome counters, with every
transition taken under one real thread lock.

The lock is a ``threading.Lock``, not an asyncio one: routes call
``FingerprintQueue.enqueue()`` through ``asyncio.to_thread`` so large batches
do not monopolize the event loop, and that check-then-mutate must exclude the
async worker's dequeue transition (#5261).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

AddOutcome = Literal["added", "queued", "processing", "full"]


@dataclass
class FingerprintQueueState:
    """Pending tracks, the one being fingerprinted, and how many finished each way."""

    queue: deque[int] = field(default_factory=deque)
    queued_set: set[int] = field(default_factory=set)  # For O(1) dedup lookup
    processing: int | None = None
    completed: int = 0
    failed: int = 0
    started_at: datetime | None = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, track_id: int, max_size: int) -> tuple[AddOutcome, int]:
        """Queue *track_id* unless it is pending or the queue is full; returns (outcome, queue size)."""
        with self.lock:
            if track_id in self.queued_set:
                return "queued", len(self.queue)
            if track_id == self.processing:
                return "processing", len(self.queue)
            if len(self.queue) >= max_size:
                return "full", len(self.queue)
            self.queue.append(track_id)
            self.queued_set.add(track_id)
            return "added", len(self.queue)

    def is_pending(self, track_id: int) -> bool:
        """True when the track is waiting in the queue or being fingerprinted right now."""
        with self.lock:
            return track_id in self.queued_set or track_id == self.processing

    def pop_next(self) -> tuple[int | None, int]:
        """Move the next track from queued to processing; returns (track_id or None, remaining).

        One atomic step, so a threaded ``add()`` can never observe the track in
        neither state and queue it a second time.
        """
        with self.lock:
            if not self.queue:
                return None, 0
            track_id = self.queue.popleft()
            self.queued_set.discard(track_id)
            self.processing = track_id
            return track_id, len(self.queue)

    def finish(self, outcome: Literal["completed", "failed", "cancelled"]) -> None:
        """Clear the in-flight track, counting it as completed or failed (a cancel counts neither)."""
        with self.lock:
            self.processing = None
            if outcome == "completed":
                self.completed += 1
            elif outcome == "failed":
                self.failed += 1

    def mark_started(self) -> None:
        with self.lock:
            self.started_at = datetime.now()

    def drop_pending(self) -> None:
        """Forget every queued and in-flight track (#6094); the counters are kept."""
        with self.lock:
            self.processing = None
            self.queue.clear()
            self.queued_set.clear()

    def snapshot(self) -> dict[str, Any]:
        """The counters as the stats endpoint reports them."""
        with self.lock:
            return {
                "queued": len(self.queue),
                "processing": self.processing,
                "completed": self.completed,
                "failed": self.failed,
                "started_at": self.started_at.isoformat() if self.started_at else None,
            }
