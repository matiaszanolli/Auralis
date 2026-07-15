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

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.config import UnifiedConfig

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
        # Serialises cache access so concurrent jobs with identical config share
        # one instance and FIFO eviction never interleaves with a read/write
        # ("dictionary changed size during iteration", #2320).
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
        HybridProcessor.__init__ (200-500 ms, CPU-bound) is offloaded to a thread
        so the event loop stays responsive while the lock is held.
        """
        async with self._lock:
            key = self.cache_key(mode, config)

            if key in self.processors:
                return self.processors.pop(key)

            # Construction is CPU-bound (200-500 ms); the factory offloads it to
            # a thread so the event loop stays responsive while the lock is held.
            processor = await self._create_processor(config)
            return processor

    async def return_to_cache(
        self, mode: str, config: UnifiedConfig, processor: HybridProcessor
    ) -> None:
        """Return a processor to the cache after job completion (#3201)."""
        async with self._lock:
            key = self.cache_key(mode, config)
            self.processors[key] = processor

            # Keep cache size bounded (max N different processor configurations).
            if len(self.processors) > self._max_cached:
                cache_keys = list(self.processors)
                if cache_keys:
                    self.processors.pop(cache_keys[0], None)
