"""
StreamlinedCacheWorker lifecycle (split from streamlined_worker.py, #5833):
start/stop, the liveness accessors lifecycle watchers read, and the 1 s loop.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging

from collections.abc import Callable, Coroutine
from typing import Any

from helpers import spawn_background_task

from .processor_close import wait_for_pending_closes
from .streamlined_processor_disposal import close_dropped_processor
from .task_cancellation import await_cancelled_task

logger = logging.getLogger(__name__)
_POLL_INTERVAL_S = 1.0  # how often the worker looks for chunks to cache (#6642)


class WorkerLifecycleMixin:
    """Background-task lifecycle; the loop body is the worker's ``_process_priorities``."""

    running: bool
    _worker_task: asyncio.Task[None] | None

    # Provided by StreamlinedCacheWorker (bound to streamlined_tiers.
    # process_priorities); async.
    _process_priorities: "Callable[[], Coroutine[Any, Any, None]]"

    async def start(self) -> None:
        """Start the background worker."""
        if not self.running:
            self.running = True
            self._worker_task = spawn_background_task(self._worker_loop(), name="streamlined_worker._worker_loop")
            logger.info("🚀 Streamlined cache worker started")

    async def stop(self) -> None:
        """Stop the background worker."""
        self.running = False
        if self._worker_task:
            self._worker_task.cancel()
            await await_cancelled_task(self._worker_task, logger)
            # Drop the finished task (#4577) — leaving it in place lets a
            # health probe landing between stop() and the next start() read a
            # done task, or a plain truthiness check report a stopped worker
            # as running.
            self._worker_task = None
        await self._close_cached_processors()
        logger.info("🛑 Streamlined cache worker stopped")

    async def _close_cached_processors(self) -> None:
        """Release every cached ChunkedAudioProcessor (#5979).

        Each holds a SeekableSource reference on the converted temp WAV of an .m4a/.aac/.wma
        track, and ConvertedWavRegistry.shutdown() deletes only unreferenced conversions, so
        processors left in the cache kept their temp files for the life of the process. Through
        close_dropped_processor like every other drop (#6551): one a render still holds (the
        cancel above only abandoned its awaiting side) closes when that render ends. The closes
        run off the loop (#6550) and are awaited here, so stop() returns with them done.
        """
        cache = getattr(self, "_processor_cache", None)
        if cache:
            for key, processor in list(cache.items()):
                close_dropped_processor(key, processor)
            cache.clear()
        await wait_for_pending_closes()

    @property
    def worker_task(self) -> asyncio.Task[None] | None:
        """The live background task, or None when not running (#4577).

        Public accessor so lifecycle watchers (``config/startup/workers.py``) don't
        reach into the private attribute.
        """
        return self._worker_task

    @property
    def is_running(self) -> bool:
        """True only while the background loop is actually alive (#4577).

        False in all three dead states: never started, stopped, and crashed
        (task done with an exception) — the last being the stale-truthiness
        case #3898 is about.
        """
        return (
            self.running
            and self._worker_task is not None
            and not self._worker_task.done()
        )

    async def _worker_loop(self) -> None:
        """
        Main worker loop - runs continuously.

        Checks every 1 second for needed chunks and processes them.
        """
        try:
            while self.running:
                await asyncio.sleep(_POLL_INTERVAL_S)

                try:
                    await self._process_priorities()
                except Exception as e:
                    logger.error(f"Error in cache worker loop: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Cache worker loop cancelled")
            raise
