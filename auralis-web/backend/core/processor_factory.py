"""
Processor Factory
~~~~~~~~~~~~~~~~~~

Unified processor factory consolidating ProcessorManager and
hybrid_processor._processor_cache into single source of truth.

This factory manages HybridProcessor instance lifecycle and caching,
eliminating ~150 lines of duplicate caching logic across 2 files.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import hashlib
import json
import logging
import threading
from collections import OrderedDict
from copy import deepcopy
from typing import Any, NamedTuple

from .env_config import get_int_env


class ProcessorCacheKey(NamedTuple):
    """#3733: structured cache key for `ProcessorFactory._processor_cache`.

    Documenting the key shape as a NamedTuple lets introspection use
    named-attribute access (`key.track_id`, `key.preset`) instead of
    positional indexing (`key[0]`). Adding a new field in the future
    (sample_rate, etc.) stays backward-compatible for callers that
    already use the named fields; positional access would silently shift.

    #4707: `intensity` is deliberately NOT a field. It was keyed on without
    ever reaching the constructed processor — `get_or_create` applies only the
    preset (`config.mastering_profile`) and optional mastering targets, and
    intensity is realised downstream as a dry/wet blend on the processor's
    OUTPUT (`core/audio_processing_pipeline.py`). Two calls differing only in
    intensity therefore built two byte-identical processors and consumed two of
    the 32 LRU slots, so an intensity slider sweep evicted genuinely distinct
    (track, preset) processors and forced redundant 200-500 ms constructions,
    each paying the full 200-500 ms HybridProcessor.__init__ (#3746 — which
    also cited a 5-thread fingerprint executor per build; that executor is
    gone, see #4744, but the construction cost is not).

    Every field here is one the processor actually consumes, matching
    `ProcessorPool.cache_key`. Contrast `targets_hash`, which #3720 added
    precisely because targets DO change the constructed processor.
    """
    track_id: int
    preset: str
    config_hash: str
    targets_hash: str

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


class ProcessorFactory:
    """
    Unified processor factory for HybridProcessor instances.

    Consolidates caching logic from:
    - processor_manager.py: ProcessorManager (track-based caching)
    - hybrid_processor.py: _processor_cache (config-based caching)

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

    Usage (config-based):
        factory = ProcessorFactory()
        processor = factory.get_or_create_from_config(
            config=my_config,
            mode="adaptive"
        )
    """

    def __init__(self) -> None:
        """Initialize processor factory."""
        # Unified cache: (track_id, preset, config_hash, targets_hash) -> HybridProcessor.
        # OrderedDict with LRU eviction (fixes #3515 / BE-NEW-57) — `cleanup_track`
        # is never called by production code, so the unbounded dict was
        # accumulating gigabytes of HybridProcessor state for any long-running
        # backend session.
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

        logger.info(f"ProcessorFactory initialized (LRU cap: {_PROCESSOR_CACHE_MAX})")

    def _get_cache_key(
        self,
        track_id: int,
        preset: str,
        config_hash: str,
        targets_hash: str = "none",
    ) -> ProcessorCacheKey:
        """
        Generate cache key for processor.

        Args:
            track_id: Track ID (use 0 for config-based caching)
            preset: Processing preset
            config_hash: Hash of config object (use "default" for default config)
            targets_hash: Hash of mastering_targets dict (use "none" if absent).
                #3720: included in the key so two callers requesting the same
                (track_id, preset) with DIFFERENT targets get different cached
                processors — eliminates the need to re-apply targets on cache
                hit (which raced with in-flight processing).

        Note:
            `intensity` is intentionally absent (#4707) — see ProcessorCacheKey.

        Returns:
            Cache key tuple
        """
        return ProcessorCacheKey(
            track_id=track_id,
            preset=preset.lower(),
            config_hash=config_hash,
            targets_hash=targets_hash,
        )

    def _get_targets_hash(self, mastering_targets: dict[str, Any] | None) -> str:
        """#3720: content hash of mastering_targets, used in the cache key.
        Returns "none" when targets are absent so existing callsites that
        don't supply targets share a single cache entry per (track, preset,
        config) — preserving the prior cache-hit behaviour for
        the common case."""
        if mastering_targets is None:
            return "none"
        try:
            payload = json.dumps(mastering_targets, sort_keys=True, default=str)
        except (TypeError, ValueError):
            # Fall back to a stable repr if the dict contains non-JSON values.
            payload = repr(sorted(mastering_targets.items()))
        return hashlib.md5(payload.encode()).hexdigest()

    def _get_config_hash(self, config: Any | None) -> str:
        """
        Get hash of config object for cache key.

        Args:
            config: UnifiedConfig instance or None

        Returns:
            Config hash string
        """
        if config is None:
            return "default"

        # Content-based hash so equivalent configs share cache entries
        config_str = json.dumps(config.to_dict(), sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

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

        Consolidates logic from:
        - ProcessorManager.get_or_create()
        - hybrid_processor._get_or_create_processor()

        Reuses the same processor instance to maintain state across chunks
        (compressor envelope followers, gain reduction tracking, etc.).

        Args:
            track_id: Track ID for cache key (use 0 for non-track processing)
            preset: Processing preset (adaptive, gentle, warm, bright, punchy)
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
        from auralis.core.config import UnifiedConfig
        from auralis.core.hybrid_processor import HybridProcessor

        # #3720: include the targets content in the cache key so two
        # callers with different targets land on different cached
        # processors. Eliminates the previous race where the cache-hit
        # re-apply of `set_fixed_mastering_targets` (#3530) mutated a
        # processor that another thread was actively iterating chunks
        # on, swapping its DSP parameters mid-track.
        config_hash = self._get_config_hash(config)
        targets_hash = self._get_targets_hash(mastering_targets)
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

        # Construction takes 200-500 ms and does not touch cache state. Keep it
        # outside the global factory lock so unrelated cold keys can construct
        # concurrently (#4689). The processor receives its own config snapshot;
        # factory preset changes must never mutate caller-owned state (#4827).
        logger.info(
            "Creating new processor: track_id=%s, preset=%s, intensity=%s",
            track_id,
            preset,
            intensity,
        )
        try:
            owned_config = deepcopy(config) if config is not None else UnifiedConfig()
            owned_config.mastering_profile = preset.lower()
            processor = HybridProcessor(owned_config)

            if mastering_targets is not None:
                processor.set_fixed_mastering_targets(deepcopy(mastering_targets))
                logger.debug("Applied fixed mastering targets to processor")
        except Exception as error:
            logger.error("Failed to create processor for track %s: %s", track_id, error)
            raise

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
                while len(self._processor_cache) > _PROCESSOR_CACHE_MAX:
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

    def get_or_create_from_config(
        self,
        config: Any | None = None,
        mode: str = "adaptive"
    ) -> Any:
        """
        Get or create processor from config (config-based caching pattern).

        Consolidates logic from hybrid_processor._get_or_create_processor().
        Used for non-track-based processing (e.g., CLI tools, batch processing).

        Args:
            config: Optional UnifiedConfig instance
            mode: Processing mode (adaptive, reference, hybrid)

        Returns:
            HybridProcessor instance
        """
        from auralis.core.config import UnifiedConfig

        # Mode selection belongs to the processor snapshot, not the caller's
        # potentially shared config (#4827). get_or_create takes one more
        # snapshot before constructing so all public factory paths have the
        # same ownership guarantee.
        owned_config = deepcopy(config) if config is not None else UnifiedConfig()
        owned_config.set_processing_mode(mode)  # type: ignore[arg-type]

        # Use get_or_create with track_id=0 for config-based caching
        return self.get_or_create(
            track_id=0,
            preset=owned_config.mastering_profile,
            intensity=1.0,
            config=owned_config
        )

    def release(self, track_id: int) -> None:
        """
        Release processor for a track.

        Removes from active tracking but keeps in cache for fast re-acquisition.

        Args:
            track_id: Track ID to release
        """
        with self._lock:
            if track_id in self._active_processors:
                self._active_processors.pop(track_id)
                logger.debug(f"Released processor for track {track_id}")

    def cleanup_track(self, track_id: int) -> None:
        """
        Clean up all processors for a track.

        Removes both from active tracking AND cache (full cleanup).

        Args:
            track_id: Track ID to clean up
        """
        with self._lock:
            # Remove from active tracking
            if track_id in self._active_processors:
                self._active_processors.pop(track_id)

            # #3733: named-attribute filter survives future key
            # extensions (e.g., adding `sample_rate`) without silently
            # shifting positional indices like `key[0]` would.
            keys_to_remove = [
                key for key in self._processor_cache
                if key.track_id == track_id
            ]

            for key in keys_to_remove:
                # Dispose before dropping the reference (#3746 set the pattern;
                # close() releases nothing today — #4744).
                self._processor_cache.pop(key).close()

            logger.info(f"Cleaned up {len(keys_to_remove)} processor(s) for track {track_id}")

    # #4618: `set_mastering_targets()` was deleted here. It was a deprecated,
    # caller-less public method that looked up the OLD-shape cache key
    # (targets_hash="none") and mutated that processor in place — a documented
    # race against any concurrent `process_chunk()` on the same instance,
    # waiting for its first caller. `get_or_create(..., mastering_targets=...)`
    # has been the whole replacement since #3720: the targets are hashed into
    # the cache key, so distinct targets land in distinct cache entries and no
    # in-place mutation of a shared processor is ever needed.

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about cached and active processors.

        Returns:
            Dictionary with processor statistics
        """
        with self._lock:
            return {
                "total_cached": len(self._processor_cache),
                "total_active": len(self._active_processors),
                "active_track_ids": list(self._active_processors.keys()),
                "cache_keys": len(self._processor_cache),
            }

    def clear_cache(self) -> None:
        """Clear all cached processors (for memory management)."""
        with self._lock:
            count = len(self._processor_cache)
            # Dispose before dropping references (#3746 set the pattern;
            # close() releases nothing today — #4744).
            for processor in self._processor_cache.values():
                processor.close()
            self._processor_cache.clear()
            self._active_processors.clear()
            logger.info(f"Cleared {count} cached processor(s)")

    @property
    def active_processors(self) -> dict[int, Any]:
        """
        Get currently active processors for monitoring.

        Returns:
            Dictionary mapping track_id to processor
        """
        with self._lock:
            return self._active_processors.copy()


# Global processor factory instance (singleton pattern)
_global_processor_factory: ProcessorFactory | None = None
_factory_lock = threading.Lock()


def get_processor_factory() -> ProcessorFactory:
    """
    Get global processor factory instance (singleton).

    This is the recommended way to access the factory for consistent
    processor caching across the application.

    Returns:
        Global ProcessorFactory instance
    """
    global _global_processor_factory

    if _global_processor_factory is None:
        with _factory_lock:
            # Double-check locking pattern
            if _global_processor_factory is None:
                _global_processor_factory = ProcessorFactory()
                logger.info("Global ProcessorFactory instance created")

    return _global_processor_factory


def create_processor_factory() -> ProcessorFactory:
    """
    Create new processor factory instance (for testing or isolation).

    Use this when you need a separate factory instance that doesn't
    share the global cache.

    Returns:
        New ProcessorFactory instance
    """
    return ProcessorFactory()
