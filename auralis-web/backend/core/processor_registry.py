"""
Process-wide ProcessorFactory registry (split from processor_factory.py,
#5833): one factory per consumer, created on first use.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import threading

from .processor_factory import ProcessorFactory

logger = logging.getLogger(__name__)

# One factory per consumer that advances a processor's cross-chunk state
# (#5311). A HybridProcessor carries EQ gain smoothing, limiter gain reduction
# and dynamics envelopes from one process() call to the next, and its
# _process_lock serializes calls without ordering them. When the proactive
# buffer or the Tier-2 cache worker resolved the same (track, preset, config,
# targets) key as a live stream, all of them fed chunks into one instance, so
# each inherited the others' state at its chunk seams — and the on-disk chunk
# cache then kept those seams. Separate factories mean separate instances,
# each seeing only its own consumer's chunks in that consumer's order.
STREAM_CONSUMER = "stream"
PROACTIVE_BUFFER_CONSUMER = "proactive_buffer"
CACHE_WORKER_CONSUMER = "cache_worker"

# Background consumers only need processors for the track(s) they are working
# on now, so their LRU caps are small; the live stream keeps
# AURALIS_PROCESSOR_CACHE_MAX. The cache worker keeps the current and previous
# track warm (see streamlined_processor_cache._PROCESSOR_CACHE_MAX).
_CONSUMER_CACHE_MAX: dict[str, int] = {
    PROACTIVE_BUFFER_CONSUMER: 2,
    CACHE_WORKER_CONSUMER: 4,
}

_processor_factories: dict[str, ProcessorFactory] = {}
_factory_lock = threading.Lock()


def get_processor_factory(consumer: str = STREAM_CONSUMER) -> ProcessorFactory:
    """
    Get the process-wide processor factory for ``consumer`` (created on first use).

    Live streaming uses the default. A background builder must pass its own
    consumer name so it never shares a stateful processor with a live
    stream (#5311).

    Returns:
        That consumer's ProcessorFactory instance
    """
    factory = _processor_factories.get(consumer)
    if factory is None:
        with _factory_lock:
            # Double-check locking pattern
            factory = _processor_factories.get(consumer)
            if factory is None:
                factory = ProcessorFactory(max_cached=_CONSUMER_CACHE_MAX.get(consumer))
                _processor_factories[consumer] = factory
                logger.info(f"ProcessorFactory for consumer '{consumer}' created")

    return factory


def all_processor_factories() -> list[ProcessorFactory]:
    """Every consumer's factory created so far (shutdown clears them all)."""
    with _factory_lock:
        return list(_processor_factories.values())
