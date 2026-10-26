"""Process-wide ordering for ``QueueService.set_queue`` and its superseders.

FastAPI builds a fresh :class:`QueueService` for every request (``Depends``), so
the lock and generation counters that make a later ``set_queue`` supersede an
earlier one cannot live on the service: two overlapping requests would hold two
services with two locks and two independent counters and never contend (#5944,
a regression of #3721).  This module-level singleton is the one thing those
instances genuinely share, like ``_TrackChangeSequencer`` (#4582) and
``PlaybackEventSequencer`` (#5294).
"""

import asyncio

from .loop_bound_lock import LoopBoundLock


class QueueSetSequencer:
    """The set-queue state lock, the engine-call lock and the generation counters."""

    def __init__(self) -> None:
        self._state_lock = LoopBoundLock()
        self._engine_lock = LoopBoundLock()
        self.next_generation = 0
        self.generation = 0

    @property
    def state_lock(self) -> asyncio.Lock:
        """Guards generation bookkeeping and the sequenced state mutation (#4825)."""
        return self._state_lock.get()

    @property
    def engine_lock(self) -> asyncio.Lock:
        """Orders engine calls; never covers a WS broadcast (#4825)."""
        return self._engine_lock.get()


queue_set_sequencer = QueueSetSequencer()
