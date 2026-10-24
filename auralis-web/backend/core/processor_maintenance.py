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

from .processor_cache_key import ProcessorCacheKey, build_cache_key, hash_config
from .targets_hash import get_targets_hash

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

    def invalidate(
        self,
        *,
        track_id: int,
        preset: str,
        mastering_targets: dict[str, Any] | None = None,
        config: Any | None = None,
    ) -> bool:
        """Discard a processor whose state can no longer be retried safely.

        A successful stateful DSP pass followed by a failed validation or
        durable write leaves that instance advanced. Removing the exact cache
        entry makes a retry construct a fresh processor instead of applying
        the same chunk twice to the advanced instance (#5274).
        """
        cache_key = build_cache_key(
            track_id,
            preset,
            hash_config(config),
            get_targets_hash(mastering_targets),
        )
        with self._lock:
            processor = self._processor_cache.pop(cache_key, None)
            if processor is None:
                return False
            if self._active_processors.get(track_id) is processor:
                self._active_processors.pop(track_id, None)

        # Dispose outside the factory lock, following the existing eviction
        # ordering. HybridProcessor.close() is currently idempotent/no-op.
        processor.close()
        logger.warning(
            "Invalidated advanced processor after post-DSP failure: "
            "track_id=%s, preset=%s",
            track_id,
            preset,
        )
        return True

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
