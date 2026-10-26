"""
ProcessorFactory cache maintenance (split from processor_factory.py, #5833):
release, invalidate, cleanup, statistics and clearing — everything that acts on
an already-populated cache, as opposed to ``get_or_create`` which fills it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import threading
from collections import OrderedDict
from typing import Any

from .processor_cache_key import ProcessorCacheKey

logger = logging.getLogger(__name__)


class ProcessorMaintenanceMixin:
    """Cache upkeep for ``ProcessorFactory``; the state lives on the factory."""

    _lock: threading.RLock
    _processor_cache: OrderedDict[ProcessorCacheKey, Any]
    _active_processors: dict[int, Any]

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

    # #4618/#3720: do not add a set_mastering_targets()-style mutator that
    # looks up a cache entry and mutates the processor in place — that races
    # any concurrent `process_chunk()` on the same instance. Mastering
    # targets go through `get_or_create(..., mastering_targets=...)`: the
    # targets are hashed into the cache key, so distinct targets land in
    # distinct cache entries and no in-place mutation is ever needed.

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
