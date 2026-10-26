"""An ``asyncio.Lock`` owned by a module-level singleton, rebound per event loop.

``asyncio.Lock`` binds to the loop running at its first contended ``acquire()``,
and reusing it from a different loop later raises "bound to a different event
loop".  The process-wide sequencers (``PlaybackEventSequencer``,
``_TrackChangeSequencer``, ``QueueSetSequencer``) are created at import time,
before any loop exists, and in tests outlive the per-case loop.  Production has
exactly one long-lived loop, so there the lock is built once and shared.
"""

import asyncio


class LoopBoundLock:
    """Hands out one ``asyncio.Lock`` per running event loop."""

    def __init__(self) -> None:
        self._lock: asyncio.Lock | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def get(self) -> asyncio.Lock:
        """Return the lock for the current running loop (must be called from one)."""
        loop = asyncio.get_running_loop()
        if self._lock is None or self._loop is not loop:
            self._lock = asyncio.Lock()
            self._loop = loop
        return self._lock
