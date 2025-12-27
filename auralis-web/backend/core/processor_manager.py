"""
Processor Manager (DEPRECATED - Phase 2 Refactoring)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

⚠️ **DEPRECATED**: This module has been replaced by ProcessorFactory in Phase 2.

**Migration**: Use `processor_factory.ProcessorFactory` instead:
```python
# OLD:
from core.processor_manager import ProcessorManager
manager = ProcessorManager()
processor = manager.get_or_create(track_id=123, preset="adaptive")

# NEW:
from core.processor_factory import ProcessorFactory
factory = ProcessorFactory()
processor = factory.get_or_create(track_id=123, preset="adaptive")
```

**Why deprecated**: ProcessorFactory consolidates both ProcessorManager and
hybrid_processor._processor_cache into a single unified caching system.

**Status**: No longer used in codebase (replaced 2025-12-16)

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
from typing import Any, Dict, Optional, Tuple

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig

logger = logging.getLogger(__name__)


class ProcessorManager:
    """
    Manages HybridProcessor instances and their lifecycle.

    **Rationale**: A single HybridProcessor instance must be maintained across
    chunk processing to preserve compressor envelope followers and gain reduction
    tracking. This prevents audio artifacts at chunk boundaries.

    The ProcessorManager centralizes this lifecycle management to:
    - Create processors with consistent configuration
    - Cache and reuse processors for the same preset
    - Track active processors for monitoring
    - Apply mastering targets and settings consistently
    """

    def __init__(self) -> None:
        """Initialize ProcessorManager."""
        # Map of (track_id, preset, intensity) -> HybridProcessor
        self._processors: Dict[Tuple[int, str, float], HybridProcessor] = {}

        # Track active processors for monitoring
        self._active_processors: Dict[int, HybridProcessor] = {}

    def get_or_create(
        self,
        track_id: int,
        preset: str = "adaptive",
        intensity: float = 1.0,
        mastering_targets: Optional[Dict[str, Any]] = None
    ) -> HybridProcessor:
        """
        Get cached processor or create new one.

        Reuses the same processor instance across chunks to maintain state
        (compressor envelope followers, gain reduction tracking, etc.).

        Args:
            track_id: Track ID for caching key
            preset: Processing preset (adaptive, gentle, warm, bright, punchy)
            intensity: Processing intensity (0.0-1.0)
            mastering_targets: Pre-computed mastering targets from fingerprint (optional)

        Returns:
            HybridProcessor instance
        """
        cache_key = (track_id, preset, intensity)

        # Check cache
        if cache_key in self._processors:
            logger.debug(f"Retrieved cached processor for track {track_id}, preset {preset}")
            return self._processors[cache_key]

        # Create new processor
        logger.info(f"Creating new processor for track {track_id}, preset {preset}")

        try:
            config = UnifiedConfig()
            config.set_processing_mode("adaptive")
            config.mastering_profile = preset.lower()

            processor = HybridProcessor(config)

            # Apply fixed mastering targets if provided (for instant toggle, 8x faster)
            if mastering_targets is not None:
                processor.set_fixed_mastering_targets(mastering_targets)
                logger.info(f"Applied fixed mastering targets to processor for track {track_id}")

            # Cache and track
            self._processors[cache_key] = processor
            self._active_processors[track_id] = processor

            return processor

        except Exception as e:
            logger.error(f"Failed to create processor for track {track_id}: {e}")
            raise

    def release(self, track_id: int) -> None:
        """
        Release processor for a track.

        Allows cleanup of resources and removal of stale processors.

        Args:
            track_id: Track ID to release
        """
        if track_id in self._active_processors:
            processor = self._active_processors.pop(track_id)
            logger.info(f"Released processor for track {track_id}")

            # Optionally clean up from main cache (but could keep for fast re-acquisition)
            # For now, just remove from active tracking

    def set_mastering_targets(
        self,
        track_id: int,
        preset: str,
        intensity: float,
        mastering_targets: Dict[str, Any]
    ) -> None:
        """
        Set mastering targets for an existing processor.

        Args:
            track_id: Track ID
            preset: Processing preset
            intensity: Processing intensity
            mastering_targets: Mastering targets dictionary
        """
        cache_key = (track_id, preset, intensity)

        if cache_key in self._processors:
            processor = self._processors[cache_key]
            processor.set_fixed_mastering_targets(mastering_targets)
            logger.info(f"Updated mastering targets for processor (track {track_id}, preset {preset})")

    @property
    def active_processors(self) -> Dict[int, HybridProcessor]:
        """
        Get currently active processors for monitoring.

        Returns:
            Dictionary mapping track_id to processor
        """
        return self._active_processors.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about cached and active processors.

        Returns:
            Dictionary with processor statistics
        """
        return {
            "total_cached": len(self._processors),
            "total_active": len(self._active_processors),
            "active_track_ids": list(self._active_processors.keys()),
        }

    def clear_cache(self) -> None:
        """Clear all cached processors (for memory management)."""
        self._processors.clear()
        self._active_processors.clear()
        logger.info("Cleared all cached processors")

    def cleanup_track(self, track_id: int) -> None:
        """
        Clean up all processors for a track.

        Args:
            track_id: Track ID to clean up
        """
        # Remove from active tracking
        if track_id in self._active_processors:
            self._active_processors.pop(track_id)

        # Remove all cache entries for this track
        keys_to_remove = [key for key in self._processors if key[0] == track_id]
        for key in keys_to_remove:
            self._processors.pop(key)

        logger.info(f"Cleaned up {len(keys_to_remove)} processor(s) for track {track_id}")
