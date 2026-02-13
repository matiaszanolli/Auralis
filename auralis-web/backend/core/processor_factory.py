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

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


class ProcessorFactory:
    """
    Unified processor factory for HybridProcessor instances.

    Consolidates caching logic from:
    - processor_manager.py: ProcessorManager (track-based caching)
    - hybrid_processor.py: _processor_cache (config-based caching)

    This factory provides:
    - Unified cache key: (track_id, preset, intensity, config_hash)
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
        # Unified cache: (track_id, preset, intensity, config_hash) -> HybridProcessor
        self._processor_cache: dict[tuple[int, str, float, str], Any] = {}

        # Active processors by track_id for monitoring
        self._active_processors: dict[int, Any] = {}

        # Thread-safe lock for cache operations
        self._lock = threading.RLock()

        logger.info("ProcessorFactory initialized")

    def _get_cache_key(
        self,
        track_id: int,
        preset: str,
        intensity: float,
        config_hash: str
    ) -> tuple[int, str, float, str]:
        """
        Generate cache key for processor.

        Args:
            track_id: Track ID (use 0 for config-based caching)
            preset: Processing preset
            intensity: Processing intensity
            config_hash: Hash of config object (use "default" for default config)

        Returns:
            Cache key tuple
        """
        return (track_id, preset.lower(), intensity, config_hash)

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

        # Use object id as hash (same instance = same hash)
        return str(id(config))

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
            intensity: Processing intensity (0.0-1.0)
            config: Optional UnifiedConfig instance
            mastering_targets: Optional pre-computed mastering targets

        Returns:
            HybridProcessor instance
        """
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        # Generate cache key
        config_hash = self._get_config_hash(config)
        cache_key = self._get_cache_key(track_id, preset, intensity, config_hash)

        with self._lock:
            # Check cache
            if cache_key in self._processor_cache:
                logger.debug(f"Retrieved cached processor: track_id={track_id}, preset={preset}")
                return self._processor_cache[cache_key]

            # Create new processor
            logger.info(f"Creating new processor: track_id={track_id}, preset={preset}, intensity={intensity}")

            try:
                # Use provided config or create default
                if config is None:
                    config = UnifiedConfig()

                # Set preset on config
                config.mastering_profile = preset.lower()

                # Create processor
                processor = HybridProcessor(config)

                # Apply fixed mastering targets if provided (8x faster processing)
                if mastering_targets is not None:
                    processor.set_fixed_mastering_targets(mastering_targets)
                    logger.debug(f"Applied fixed mastering targets to processor")

                # Cache processor
                self._processor_cache[cache_key] = processor

                # Track active processor by track_id
                if track_id > 0:
                    self._active_processors[track_id] = processor

                logger.info(f"Processor created and cached: {len(self._processor_cache)} total in cache")
                return processor

            except Exception as e:
                logger.error(f"Failed to create processor for track {track_id}: {e}")
                raise

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
        from auralis.core.unified_config import UnifiedConfig

        # Use config hash as cache key, track_id=0 for config-based
        if config is None:
            config = UnifiedConfig()

        # Set processing mode
        config.set_processing_mode(mode)  # type: ignore[arg-type]

        # Use get_or_create with track_id=0 for config-based caching
        return self.get_or_create(
            track_id=0,
            preset=config.mastering_profile,
            intensity=1.0,
            config=config
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

            # Remove all cache entries for this track
            keys_to_remove = [
                key for key in self._processor_cache
                if key[0] == track_id
            ]

            for key in keys_to_remove:
                self._processor_cache.pop(key)

            logger.info(f"Cleaned up {len(keys_to_remove)} processor(s) for track {track_id}")

    def set_mastering_targets(
        self,
        track_id: int,
        preset: str,
        intensity: float,
        mastering_targets: dict[str, Any],
        config: Any | None = None
    ) -> None:
        """
        Set mastering targets for an existing processor.

        Args:
            track_id: Track ID
            preset: Processing preset
            intensity: Processing intensity
            mastering_targets: Mastering targets dictionary
            config: Optional config for cache key
        """
        config_hash = self._get_config_hash(config)
        cache_key = self._get_cache_key(track_id, preset, intensity, config_hash)

        with self._lock:
            if cache_key in self._processor_cache:
                processor = self._processor_cache[cache_key]
                processor.set_fixed_mastering_targets(mastering_targets)
                logger.debug(f"Updated mastering targets for processor (track {track_id}, preset {preset})")

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


# Convenience functions (backward compatibility with hybrid_processor pattern)

def process_adaptive(
    target: Any,
    config: Any | None = None
) -> Any:
    """
    Quick adaptive processing function (uses global factory).

    Consolidates logic from hybrid_processor.process_adaptive().

    Args:
        target: Target audio file path or array
        config: Optional UnifiedConfig instance

    Returns:
        Processed audio array
    """
    factory = get_processor_factory()
    processor = factory.get_or_create_from_config(config, mode="adaptive")
    result = processor.process(target)
    assert result is not None
    return result


def process_reference(
    target: Any,
    reference: Any,
    config: Any | None = None
) -> Any:
    """
    Quick reference-based processing function (uses global factory).

    Consolidates logic from hybrid_processor.process_reference().

    Args:
        target: Target audio file path or array
        reference: Reference audio file path or array
        config: Optional UnifiedConfig instance

    Returns:
        Processed audio array
    """
    factory = get_processor_factory()
    processor = factory.get_or_create_from_config(config, mode="reference")
    result = processor.process(target, reference)
    assert result is not None
    return result


def process_hybrid(
    target: Any,
    reference: Any | None = None,
    config: Any | None = None
) -> Any:
    """
    Quick hybrid processing function (uses global factory).

    Consolidates logic from hybrid_processor.process_hybrid().

    Args:
        target: Target audio file path or array
        reference: Optional reference audio file path or array
        config: Optional UnifiedConfig instance

    Returns:
        Processed audio array
    """
    factory = get_processor_factory()
    processor = factory.get_or_create_from_config(config, mode="hybrid")
    result = processor.process(target, reference)
    assert result is not None
    return result
