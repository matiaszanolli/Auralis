"""
Processor Factory
~~~~~~~~~~~~~~~~~~

Unified processor factory: the single source of truth for cached
HybridProcessor instances. It absorbed the track-based cache of a former
``ProcessorManager`` class (processor_manager.py — no longer in the tree) and
the config-based hybrid_processor_singleton._processor_cache.

This factory manages HybridProcessor instance lifecycle and caching,
eliminating ~150 lines of duplicate caching logic across 2 files.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import threading
from collections import OrderedDict
from typing import Any

from .env_config import get_int_env
from .processor_cache_key import (
    ProcessorCacheKey,
    build_cache_key,
    hash_config,
)
from .processor_lease import ProcessorLeaseMixin
from .processor_maintenance import ProcessorMaintenanceMixin
from .targets_hash import get_targets_hash

logger = logging.getLogger(__name__)

# LRU bound for the processor cache. A HybridProcessor instance holds
# EQ filter banks, compressor envelope followers, mastering targets, and
# fingerprint analysers — roughly 1-200 MB each depending on preset. At
# 32 entries the cache caps at a few GB worst-case, easily within reach
# of typical desktop RAM, while still amortising creation cost across
# rapid track switches and A/B preset comparisons (fixes #3515 / BE-NEW-57).
# Override via AURALIS_PROCESSOR_CACHE_MAX (#3917) — see
# auralis-web/backend/CONFIG.md.
_PROCESSOR_CACHE_MAX = get_int_env("AURALIS_PROCESSOR_CACHE_MAX", 32)


class ProcessorFactory(ProcessorLeaseMixin, ProcessorMaintenanceMixin):
    """
    Unified processor factory for HybridProcessor instances.

    Consolidates track-based caching (from the former ProcessorManager, see
    the module docstring) with config-based caching
    (hybrid_processor_singleton.py: _processor_cache).

    This factory provides:
    - Unified cache key: (track_id, preset, config_hash, targets_hash)
    - Thread-safe operations with RLock
    - Lifecycle management (create, release, cleanup)
    - Statistics and monitoring
    - Support for both track-based and config-based usage patterns

    Usage (track-based):
        factory = ProcessorFactory()
        processor = factory.get_or_create(
            track_id=123,
            preset="adaptive",
            intensity=1.0,
            mastering_targets=targets
        )

    """

    def __init__(self, max_cached: int | None = None) -> None:
        """Initialize processor factory.

        ``max_cached`` overrides the LRU cap for this instance; ``None`` keeps
        ``_PROCESSOR_CACHE_MAX``, read at eviction time so it stays patchable.
        """
        self._max_cached = max_cached
        # Unified cache: (track_id, preset, config_hash, targets_hash) -> HybridProcessor.
        # OrderedDict with LRU eviction (fixes #3515 / BE-NEW-57) — the
        # unbounded dict it replaced accumulated gigabytes of HybridProcessor
        # state for any long-running backend session.
        # #3720: cache key includes targets_hash so different
        # mastering_targets for the same (track_id, preset) get distinct
        # cached processors instead of racing on a re-apply. #4707 dropped
        # intensity from the key — the processor never consumed it.
        # #3733: the key shape is documented as a NamedTuple
        # (ProcessorCacheKey) so introspection — e.g., `cleanup_for_track`
        # filtering by `track_id` — uses named-attribute access and
        # survives future extensions (adding `sample_rate` etc.) without
        # silently shifting positional indices.
        self._processor_cache: OrderedDict[ProcessorCacheKey, Any] = OrderedDict()

        # Active processors by track_id for monitoring
        self._active_processors: dict[int, Any] = {}

        # Thread-safe lock for cache operations
        self._lock = threading.RLock()

        logger.info(f"ProcessorFactory initialized (LRU cap: {self._cache_cap()})")

    def _cache_cap(self) -> int:
        return self._max_cached if self._max_cached is not None else _PROCESSOR_CACHE_MAX

    def _get_cache_key(
        self,
        track_id: int,
        preset: str,
        config_hash: str,
        targets_hash: str = "none",
    ) -> ProcessorCacheKey:
        """See :func:`processor_cache_key.build_cache_key`."""
        return build_cache_key(track_id, preset, config_hash, targets_hash)

    def _get_config_hash(self, config: Any | None) -> str:
        """See :func:`processor_cache_key.hash_config`."""
        return hash_config(config)

    def get_or_create(
        self,
        track_id: int = 0,
        preset: str = "adaptive",
        intensity: float = 1.0,
        config: Any | None = None,
        mastering_targets: dict[str, Any] | None = None
    ) -> Any:
        """
        Get cached processor or create new one.

        Consolidates logic from hybrid_processor_singleton._get_or_create_processor()
        and the former ProcessorManager.get_or_create() (see the module docstring).

        Reuses the same processor instance to maintain state across chunks
        (compressor envelope followers, gain reduction tracking, etc.).

        Args:
            track_id: Track ID for cache key (use 0 for non-track processing)
            preset: Processing preset (only 'adaptive' is valid)
            intensity: Processing intensity (0.0-1.0). Logged for
                diagnostics and accepted for API stability, but NOT part
                of the cache key — it is applied downstream as a dry/wet
                blend on the processor's output, never at construction
                (#4707).
            config: Optional UnifiedConfig instance
            mastering_targets: Optional pre-computed mastering targets

        Returns:
            HybridProcessor instance
        """
        # #3720: include the targets content in the cache key so two
        # callers with different targets land on different cached
        # processors. Eliminates the previous race where the cache-hit
        # re-apply of `set_fixed_mastering_targets` (#3530) mutated a
        # processor that another thread was actively iterating chunks
        # on, swapping its DSP parameters mid-track.
        config_hash = self._get_config_hash(config)
        targets_hash = get_targets_hash(mastering_targets)
        cache_key = self._get_cache_key(
            track_id, preset, config_hash, targets_hash
        )

        with self._lock:
            cached = self._processor_cache.get(cache_key)
            if cached is not None:
                self._processor_cache.move_to_end(cache_key)
                logger.debug(
                    "Retrieved cached processor: track_id=%s, preset=%s",
                    track_id,
                    preset,
                )
                return cached

        processor = self._build_processor(track_id, preset, intensity, config, mastering_targets)

        evicted: list[tuple[ProcessorCacheKey, Any]] = []
        with self._lock:
            # Another thread may have populated this key while construction was
            # in flight. Keep the established cached instance and reclaim the
            # redundant build so exactly one live processor survives per key.
            cached = self._processor_cache.get(cache_key)
            if cached is not None:
                self._processor_cache.move_to_end(cache_key)
                cache_size = len(self._processor_cache)
            else:
                self._processor_cache[cache_key] = processor
                while len(self._processor_cache) > self._cache_cap():
                    evicted_key, evicted_processor = self._processor_cache.popitem(
                        last=False
                    )
                    evicted.append((evicted_key, evicted_processor))
                    if (
                        evicted_key.track_id > 0
                        and self._active_processors.get(evicted_key.track_id)
                        is evicted_processor
                    ):
                        self._active_processors.pop(evicted_key.track_id, None)

                if track_id > 0:
                    self._active_processors[track_id] = processor
                cache_size = len(self._processor_cache)

        if cached is not None:
            processor.close()
            logger.debug(
                "Closed redundant processor build: track_id=%s, preset=%s",
                track_id,
                preset,
            )
            return cached

        for evicted_key, evicted_processor in evicted:
            # Dispose outside the cache lock — the ordering #3746 established.
            # close() releases nothing today (#4744); it is the seam, not a
            # thread-pool reclaim.
            evicted_processor.close()
            logger.info(
                "ProcessorFactory: LRU-evicted processor for cache_key %s",
                evicted_key,
            )

        logger.info("Processor created and cached: %s total in cache", cache_size)
        return processor

