"""
Streamlined Worker Processor Disposal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Lease and close lifecycle for the processors ``StreamlinedCacheWorker`` caches,
split out of ``core/streamlined_processor_cache.py`` (#6695): marking a
processor in use for a render, closing one that drops out of the cache, and
discarding one whose render timed out. Distinct from ``core/processor_lease.py``
and ``core/chunk_processor_lease.py``, which lease ``HybridProcessor`` instances
from the ``ProcessorFactory`` to a stream.

The lease table is touched only on the event loop, so it takes no lock. Closes
run off the loop (``core/processor_close.py``, #6550).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from core.processor_close import close_off_loop

if TYPE_CHECKING:
    from core.streamlined_processor_cache import ProcessorCacheKey


logger = logging.getLogger(__name__)

# Processors a render is running in right now (id -> renders), and dropped ones whose close waits for
# the last of them (#5064). Touched only on the event loop, so no lock.
_leases: dict[int, int] = {}
_close_when_idle: dict[int, tuple["ProcessorCacheKey", Any]] = {}


@contextmanager
def leased(processor: Any) -> Iterator[None]:
    """Mark ``processor`` in use for the duration of a render.

    An eviction, track-change prune or timeout discard that lands meanwhile cannot ``close()`` it
    (which would rmtree the temp WAV under the render's thread, #5064); it is closed here when the
    last lease ends instead.
    """
    key = id(processor)
    _leases[key] = _leases.get(key, 0) + 1
    try:
        yield
    finally:
        remaining = _leases[key] - 1
        if remaining:
            _leases[key] = remaining
        else:
            del _leases[key]
            deferred = _close_when_idle.pop(key, None)
            if deferred is not None:
                close_off_loop(*deferred)


def close_dropped_processor(cache_key: "ProcessorCacheKey", processor: Any) -> None:
    """Release a dropped processor's temp WAV, if it made one (#4737).

    The single close-on-drop point for every path that removes an entry from ``_processor_cache`` —
    LRU eviction in :func:`~core.streamlined_processor_cache.remember_processor`, the track-change prune in
    :func:`~core.streamlined_processor_cache.prune_processors_for_track` (#5062) and the timeout eviction in
    :func:`discard_timed_out_processor` (#5059) — so a future removal path can't reintroduce the leak
    by forgetting to close. A processor with a render in flight is closed when :func:`leased` ends
    (#5064). Never raises: a cleanup failure must not break the caller's eviction/prune loop.
    """
    if id(processor) in _leases:
        _close_when_idle[id(processor)] = (cache_key, processor)
        return
    close_off_loop(cache_key, processor)


def discard_timed_out_processor(
    worker: Any,
    cache_key: "ProcessorCacheKey",
    processor: Any,
    pending: asyncio.Future[Any],
) -> None:
    """Evict a processor whose chunk render timed out; close it once that render ends (#5059).

    ``asyncio.wait_for`` cancels only the awaiting side: the thread running
    ``process_chunk`` keeps going inside ``processor``. Left cached, the next
    1 Hz tick handed that same busy instance straight back out, and the orphan
    could still write its level history after the worker had moved on. The
    same poison-and-discard rule as ``ProcessorPool.discard()`` (#4727).

    Closing is deferred to ``pending``'s completion, because ``close()`` would
    otherwise pull the temp WAV (#4737) out from under the running render.
    Only an entry this call actually removes is closed here: LRU eviction and
    the track-change prune close what they drop themselves.
    """
    evicted = worker._processor_cache.get(cache_key) is processor
    if evicted:
        del worker._processor_cache[cache_key]
        if cache_key not in worker._build_waiters:
            worker._processor_build_locks.pop(cache_key, None)

    def _on_render_done(fut: asyncio.Future[Any]) -> None:
        # Retrieve the outcome so a late failure is not reported as "never
        # retrieved"; the timeout itself was already logged by the caller.
        if not fut.cancelled() and fut.exception() is not None:
            logger.debug(f"Timed-out render for {cache_key} later failed: {fut.exception()}")
        if evicted:
            close_dropped_processor(cache_key, processor)

    pending.add_done_callback(_on_render_done)
