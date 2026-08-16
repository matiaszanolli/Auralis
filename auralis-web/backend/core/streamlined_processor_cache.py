"""
Streamlined Worker Processor Cache
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

LRU processor cache plus per-key build-lock bookkeeping for
``StreamlinedCacheWorker``, split out of ``core/streamlined_worker.py`` (#5037)
so the bookkeeping with its own bug history (#4521, #4369, #4737, #5062) no
longer shares a module with tier-priority scheduling.

The state itself still lives on the worker (``_processor_cache``,
``_processor_build_locks``, ``_build_waiters``) — these are functions over that
state, passed explicitly, not a second owner of it.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from collections import OrderedDict
from typing import Any


logger = logging.getLogger(__name__)


# (track_id, preset, bucketed intensity) — the identity of a cached processor.
ProcessorCacheKey = tuple[int, str | None, float]

# LRU cap for `_processor_cache` (#4521). Sized against the worker's actual
# working set: the live track needs two entries (original + processed) and the
# previous track — kept warm for the back button — needs two more, so 4 is the
# steady-state floor. 8 leaves room for a preset switch on both tracks without
# thrashing, and is deliberately smaller than ProcessorFactory's cap of 32
# because these are wrappers over factory-owned processors, not the processors
# themselves.
#
# `streamlined_worker` imports this name and reads it at call time, so that
# module stays the documented patch point for the cap.
_PROCESSOR_CACHE_MAX = 8

# Intensity is quantised into the cache key at one decimal (#4521), matching
# `cache.manager.CachedChunk.key()`'s `{self.intensity:.1f}`. The chunk cache
# already treats every intensity inside a 0.1 bucket as the same cached chunk,
# so building one processor per bucket is the consistent choice — without this,
# a UI slider drag mints a distinct processor per intermediate float while the
# chunks they produce all collapse onto the same cache entry.
_INTENSITY_KEY_DECIMALS = 1


def intensity_key(intensity: float) -> float:
    """Bucket an intensity to the chunk cache's own 0.1 granularity (#4521)."""
    return round(float(intensity), _INTENSITY_KEY_DECIMALS)


def close_dropped_processor(cache_key: ProcessorCacheKey, processor: Any) -> None:
    """Release a dropped processor's temp WAV, if it made one (#4737).

    The single close-on-drop point for every path that removes an entry
    from ``_processor_cache`` — LRU eviction in :func:`remember_processor` and
    the track-change prune in :func:`prune_processors_for_track` (#5062) — so a
    future third removal path can't reintroduce the leak by forgetting to
    close. Never allowed to raise: a cleanup failure here would otherwise break
    the caller's eviction/prune loop.
    """
    try:
        processor.close()
    except Exception as exc:
        logger.warning(f"Failed to close dropped processor {cache_key}: {exc}")


def remember_processor(
    cache: "OrderedDict[ProcessorCacheKey, Any]",
    build_locks: dict[ProcessorCacheKey, asyncio.Lock],
    cache_key: ProcessorCacheKey,
    processor: Any,
    max_size: int,
) -> None:
    """Insert a processor as most-recently-used and evict past the cap (#4521).

    This is the single bounded-insert point, reached from ``_process_chunk``
    — which is on *both* routes into the cache (``_build_tier2_cache`` and
    ``trigger_immediate_processing``), so no insertion escapes the bound.

    Evicted entries ARE now closed (#4737). This docstring previously said
    the opposite, and the reasoning was sound at the time: a
    ``ChunkedAudioProcessor`` held no resource of its own. That changed when
    it gained a ``SeekableSource``, which for ``.m4a``/``.aac``/``.wma``
    owns a temp WAV — dropping such an entry without closing it leaks that
    file for the process lifetime.

    ``ChunkedAudioProcessor.close()`` releases *only* that temp dir. The
    original caution still holds and is honoured there: ``self.processor``
    is a *shared* ``HybridProcessor`` owned by the ``ProcessorFactory``
    singleton, which runs its own LRU with ``close()``
    (``processor_factory.py:250-264``). Closing that from here would tear
    down a processor another live ``ChunkedAudioProcessor`` — or the
    factory's own cache — is still using.
    """
    cache[cache_key] = processor
    cache.move_to_end(cache_key)

    while len(cache) > max_size:
        evicted_key, evicted = cache.popitem(last=False)
        close_dropped_processor(evicted_key, evicted)
        # Drop the matching build lock in lockstep (#4369 inherits the same
        # unbounded growth). A lock held by an in-flight build keeps working
        # — the holder retains its own reference — and a later miss for the
        # same key simply creates a fresh one.
        build_locks.pop(evicted_key, None)
        logger.debug(f"LRU-evicted cached processor for {evicted_key}")


def prune_processors_for_track(
    cache: "OrderedDict[ProcessorCacheKey, Any]",
    build_locks: dict[ProcessorCacheKey, asyncio.Lock],
    build_waiters: dict[ProcessorCacheKey, int],
    track_id: int,
) -> tuple["OrderedDict[ProcessorCacheKey, Any]", dict[ProcessorCacheKey, asyncio.Lock]]:
    """Drop every entry that isn't for ``track_id``, closing what it drops.

    Evict processors for the old track so they can be GC'd, closing each to
    release its temp WAV if it made one (#5062) — via the same
    :func:`close_dropped_processor` helper LRU eviction uses, so this second
    removal path can't omit the cleanup #4737 added to the first. This is an
    *early* release on top of the LRU cap (#4521), not the bound itself — it is
    unreachable once the track is fully cached.

    Returns the replacement ``(cache, build_locks)`` for the caller to install.
    """
    kept_cache: "OrderedDict[ProcessorCacheKey, Any]" = OrderedDict()
    for k, v in cache.items():
        if k[0] == track_id:
            kept_cache[k] = v
        else:
            close_dropped_processor(k, v)
    # Prune build locks for evicted keys too (#4369) so they don't
    # accumulate. Keys with an in-flight build are kept (#4521): dropping
    # a lock someone is still queued on lets a later caller mint a second
    # one for the same key and build concurrently.
    kept_locks = {
        k: v
        for k, v in build_locks.items()
        if k[0] == track_id or k in build_waiters
    }
    return kept_cache, kept_locks


async def get_or_build_processor(
    worker: Any,
    cache_key: ProcessorCacheKey,
    filepath: str,
) -> Any:
    """Return the cached ``ChunkedAudioProcessor`` for ``cache_key``, building it once.

    ``worker`` owns the state this reads and mutates (``_processor_cache``,
    ``_processor_build_locks``, ``_build_waiters``, ``_remember_processor``);
    it is dereferenced fresh on every access because a track change can swap
    the dicts out across any of the awaits below.
    """
    # Import here to avoid circular dependency
    from core.chunked_processor import ChunkedAudioProcessor

    processor = worker._processor_cache.get(cache_key)
    if processor is not None:
        # Refresh recency so the LRU cap evicts genuinely cold entries
        # rather than the actively-used one (#4521).
        worker._processor_cache.move_to_end(cache_key)
    if processor is None:
        # Serialize construction per cache_key so concurrent callers
        # (trigger_immediate_processing vs _worker_loop) don't each build
        # a redundant processor and overwrite one another (#4369).
        # dict.setdefault is atomic on the single-threaded loop, so the
        # lock lookup itself is race-free.
        build_lock = worker._processor_build_locks.setdefault(cache_key, asyncio.Lock())
        # Count ourselves in before awaiting (#4521) so the cleanup below
        # can tell "nobody is using this lock" from "a waiter is queued
        # on it". Dropping a lock that still has waiters would let a
        # later caller mint a second lock for the same key and rebuild
        # concurrently — reopening #4369 on the build-failure path.
        worker._build_waiters[cache_key] = worker._build_waiters.get(cache_key, 0) + 1
        try:
            async with build_lock:
                # Re-check under the lock: another task may have built it
                # while we awaited the lock.
                processor = worker._processor_cache.get(cache_key)
                if processor is None:
                    # Offload — ChunkedAudioProcessor.__init__ does a sync
                    # SoundFile open for metadata, a sync fingerprint/DB
                    # lookup, and sync HybridProcessor construction (200-500ms
                    # CPU-bound); this worker loop ticks every 1s, so running
                    # it inline stalls the event loop (and any in-flight stream
                    # chunk sends) for that whole duration on every cache miss
                    # (fixes #3817 / BE-PF-3).
                    processor = await asyncio.to_thread(
                        ChunkedAudioProcessor,
                        track_id=cache_key[0],
                        filepath=filepath,
                        preset=cache_key[1],  # None for original
                        # Build at the bucketed intensity, not the raw one
                        # (#4521), so the processor genuinely matches the
                        # key it is stored under — and so its chunk
                        # filenames (which embed self.intensity) are
                        # deterministic per bucket instead of depending on
                        # which slider value happened to miss first.
                        intensity=cache_key[2]
                    )
                    worker._remember_processor(cache_key, processor)
        finally:
            # Last one out drops an orphaned lock (#4521). If the build
            # succeeded the key is in the cache and the lock stays,
            # evicted later in lockstep by _remember_processor; if it
            # raised, nothing would ever have removed it.
            remaining = worker._build_waiters[cache_key] - 1
            if remaining:
                worker._build_waiters[cache_key] = remaining
            else:
                del worker._build_waiters[cache_key]
                if cache_key not in worker._processor_cache:
                    worker._processor_build_locks.pop(cache_key, None)

    # After the block above `processor` is always set (cache hit, or
    # built under the lock). Assert it so the nested-reassign flow is
    # visible to type-checkers.
    assert processor is not None
    return processor
