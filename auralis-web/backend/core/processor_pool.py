#!/usr/bin/env python3

"""
Processor instance pool for the ProcessingEngine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Caches expensive HybridProcessor instances so that jobs with identical
configuration reuse one instance instead of each allocating ~200 MB. Extracted
from processing_engine.py (#4250); the cache-key derivation, lock semantics, and
pop-on-acquire / return-after-use lifecycle are unchanged (preserves #2218,
#3528/BE-NEW-70, #2320, #3201).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor

logger = logging.getLogger(__name__)


class ProcessorPool:
    """LRU-ish cache of reusable HybridProcessor instances keyed by config."""

    def __init__(
        self,
        create_processor: Callable[[UnifiedConfig], Awaitable[HybridProcessor]],
        max_cached: int = 5,
    ) -> None:
        # Construction is delegated to a caller-supplied async factory so the
        # HybridProcessor symbol stays referenced in the engine's module
        # namespace — tests that `patch('core.processing_engine.HybridProcessor')`
        # keep intercepting instantiation after this extraction (#4250).
        self._create_processor = create_processor
        self.processors: dict[str, HybridProcessor] = {}
        # Serialises cache dictionary access. Processor construction deliberately
        # happens after releasing it so unrelated cold keys do not block one
        # another (#4689).
        self._lock: asyncio.Lock = asyncio.Lock()
        self._max_cached: int = max_cached

    def cache_key(self, mode: str, config: UnifiedConfig) -> str:
        """
        Generate a cache key for processor instance caching.

        Processors can be reused across jobs if they have identical processing
        mode and key configuration parameters (sample rate, EQ target, dynamics
        params). This avoids expensive reinitialization for repeated configs.
        """
        # Include mode, sample rate, adaptive mode, and an explicit set of
        # the actually-relevant settings (#2218 + fixes #3528 / BE-NEW-70).
        # Prior code hashed `vars(config)`; the @dataclass __repr__ on
        # AdaptiveConfig only covers declared fields, so dynamically-attached
        # attributes (eq_gains, compressor, target_lufs, gain, genre_override)
        # were silently excluded from the hash and two jobs with different
        # EQ settings produced identical cache keys. Also: `processing_mode`
        # is not a UnifiedConfig attribute — that slot collapsed to
        # 'unknown' for every key. Switched to config.adaptive.mode.
        adaptive = getattr(config, "adaptive", None)
        key_parts: list[str] = [
            mode,
            str(config.internal_sample_rate),
            getattr(adaptive, "mode", "unknown") if adaptive else "unknown",
            getattr(config, "mastering_profile", ""),
            repr(getattr(adaptive, "eq_gains", None)) if adaptive else "",
            repr(getattr(adaptive, "compressor", None)) if adaptive else "",
            repr(getattr(adaptive, "target_lufs", None)) if adaptive else "",
            repr(getattr(adaptive, "gain", None)) if adaptive else "",
            repr(getattr(adaptive, "genre_override", None)) if adaptive else "",
        ]
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()

    async def get_or_create(self, mode: str, config: UnifiedConfig) -> HybridProcessor:
        """
        Get a cached processor instance or create a new one.

        The instance is POPPED from the cache so no concurrent job shares it
        (#3201). The caller must return it via return_to_cache() after use.
        HybridProcessor.__init__ (200-500 ms, CPU-bound) runs outside the cache
        lock so a cold key cannot stall acquisitions for other keys (#4689).
        """
        key = self.cache_key(mode, config)
        async with self._lock:
            cached = self.processors.pop(key, None)
        if cached is not None:
            return cached

        processor = await self._create_processor(config)

        # A processor may have been returned for this key while construction
        # was in flight. Prefer that warm cached lease and close the redundant
        # new instance rather than leaking its fingerprint executor.
        async with self._lock:
            cached = self.processors.pop(key, None)
        if cached is not None:
            try:
                processor.close()
            except Exception as close_err:  # pragma: no cover - defensive
                logger.warning("Failed to close redundant processor: %s", close_err)
            return cached

        return processor

    async def return_to_cache(
        self, mode: str, config: UnifiedConfig, processor: HybridProcessor
    ) -> None:
        """Return a processor to the cache after job completion (#3201)."""
        to_close: list[HybridProcessor] = []
        async with self._lock:
            key = self.cache_key(mode, config)
            replaced = self.processors.get(key)
            if replaced is not None and replaced is not processor:
                to_close.append(replaced)
            self.processors[key] = processor

            # Keep cache size bounded (max N different processor configurations).
            #
            # Close the evicted instance (#4370). ProcessorFactory closes on
            # every eviction path; this one did not, which also defeats the
            # #4567 fix — returning a processor here could silently leak a
            # different one. The original #3746 rationale (fingerprint_analyzer
            # owns a 5-thread executor the threading module keeps reachable) no
            # longer holds: HybridProcessor.close() releases nothing today
            # (#4744). The call stays because it is the disposal seam a future
            # resource will arrive through, not because it reclaims threads.
            #
            # Evicting `cache_keys[0]` IS least-recently-used here, despite
            # looking like plain insertion-order FIFO — #4370 read it as FIFO
            # from the pre-#4250 inline version, where a cache *hit* left the
            # entry in place. get_or_create() now POPS on hit (#3201), so the key
            # is always absent when it comes back through this method and the
            # assignment above appends it. Insertion order therefore tracks
            # last-return order, and the oldest key is the least recently used.
            # Do not "fix" this into an OrderedDict + move_to_end without first
            # re-checking that invariant — see test_lru_not_fifo_eviction.
            if len(self.processors) > self._max_cached:
                cache_keys = list(self.processors)
                if cache_keys:
                    evicted = self.processors.pop(cache_keys[0], None)
                    if evicted is not None and all(
                        evicted is not stale for stale in to_close
                    ):
                        to_close.append(evicted)

        # close() is called outside the cache critical section: it is the
        # sub-component disposal seam and must not extend the lock even once it
        # regains substance (#4744 — it releases nothing today). This also
        # drops an idle same-key instance replaced by a later exclusive lease.
        for stale_processor in to_close:
            try:
                stale_processor.close()
            except Exception as close_err:  # pragma: no cover - defensive
                logger.warning("Failed to close evicted processor: %s", close_err)

    async def close_all(self) -> None:
        """Drain and close every cached processor (#5061).

        Mirrors ProcessorFactory's shutdown-time cache clear — this pool had no
        equivalent, so its cached instances were never dropped on backend
        shutdown. (What #3746 originally reclaimed here, a 5-thread executor, is
        gone; close() releases nothing today — see #4744.) Pops everything out
        under the lock, then closes
        outside it (matching return_to_cache's existing pattern), tolerating
        individual close() failures so one bad instance can't abort the drain.
        """
        async with self._lock:
            to_close = list(self.processors.values())
            self.processors.clear()

        for stale_processor in to_close:
            try:
                stale_processor.close()
            except Exception as close_err:  # pragma: no cover - defensive
                logger.warning("Failed to close pooled processor during drain: %s", close_err)

    async def discard(self, processor: HybridProcessor) -> None:
        """Close a processor without caching it (#4727).

        Used when a processor may still be in use by an orphaned thread — a
        DSP call that `asyncio.wait_for` timed out on only cancels the
        asyncio-side wrapper future, not the underlying OS thread, so the
        instance's internal state may still be mutated after the timeout
        fires. Caching it would let the next job with the same `(mode,
        config)` pop and reuse an instance the orphaned thread is still
        touching. Reuses the same close-and-log pattern as LRU eviction
        above rather than a second cleanup path.
        """
        try:
            processor.close()
        except Exception as close_err:  # pragma: no cover - defensive
            logger.warning("Failed to close discarded processor: %s", close_err)
