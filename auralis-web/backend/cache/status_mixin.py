"""
Streamlined Cache Status and Warming
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Per-track cache status, hit/miss statistics and immediate Tier 1 warming for
StreamlinedCacheManager. Split out of cache/manager.py (#5238).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from .eviction_mixin import CacheEvictionMixin
from .models import TIER1_MAX_CHUNKS, CachedChunk, TrackCacheStatus

logger = logging.getLogger(__name__)


class CacheStatusMixin(CacheEvictionMixin):
    """Cache status/statistics reporting and Tier 1 warming.

    State is initialized by StreamlinedCacheManager.__init__, not here —
    declared here only so type checkers know this mixin depends on it.
    """

    tier1_hits: int
    tier1_misses: int
    tier2_hits: int
    tier2_misses: int
    _lock: asyncio.Lock

    def get_track_cache_status(self, track_id: int) -> TrackCacheStatus | None:
        """Get cache status for a track."""
        return self.track_status.get(track_id)

    def is_track_fully_cached(self, track_id: int) -> bool:
        """Check if track is fully cached in Tier 2."""
        status = self.track_status.get(track_id)
        return status.cache_complete if status else False

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        # Real on-disk sizes (#4793), not the nominal per-chunk estimate —
        # see _tier_size_mb.
        tier1_size_mb = self._tier_size_mb(self.tier1_cache)
        tier2_size_mb = self._tier_size_mb(self.tier2_cache)

        # tier1_misses and tier2_misses both describe the same full-cache miss;
        # do not double-count it in overall request/miss totals (#5252).
        total_requests = self.tier1_hits + self.tier2_hits + self.tier1_misses

        return {
            "tier1": {
                "chunks": len(self.tier1_cache),
                "size_mb": tier1_size_mb,
                "hits": self.tier1_hits,
                "misses": self.tier1_misses,
                "hit_rate": self.tier1_hits / max(1, self.tier1_hits + self.tier1_misses)
            },
            "tier2": {
                "chunks": len(self.tier2_cache),
                "size_mb": tier2_size_mb,
                "hits": self.tier2_hits,
                "misses": self.tier2_misses,
                "hit_rate": self.tier2_hits / max(1, self.tier2_hits + self.tier2_misses),
            },
            "overall": {
                "total_chunks": len(self.tier1_cache) + len(self.tier2_cache),
                "total_size_mb": tier1_size_mb + tier2_size_mb,
                "total_hits": self.tier1_hits + self.tier2_hits,
                "total_misses": self.tier1_misses,
                "overall_hit_rate": (self.tier1_hits + self.tier2_hits) / max(1, total_requests),
                # (#4785) Belongs under "overall", not "tier2" — schemas.OverallCacheStats,
                # standardizedAPIClient.ts and types/api.ts all read it from here.
                "tracks_cached": len({c.track_id for c in self.tier2_cache.values()})
            },
            "tracks": {
                track_id: {
                    "track_id": track_id,
                    "completion_percent": status.get_completion_percent(),
                    "fully_cached": status.is_fully_cached(),
                    "total_chunks": status.total_chunks,
                    "cached_original": len(status.cached_chunks_original),
                    "cached_processed": len(status.cached_chunks_processed)
                }
                for track_id, status in self.track_status.items()
            }
        }

    async def warm_tier1_immediately(
        self,
        track_id: int,
        chunk_paths: list[tuple[int, Path, str | None]],
        intensity: float = 1.0,
        file_signature: str = ""
    ) -> int:
        """
        Immediately warm Tier 1 cache with pre-processed chunks.

        This proactively loads the current and next chunks into Tier 1 cache
        to ensure instant playback continuity and fast preset switching.

        Args:
            track_id: Track ID
            chunk_paths: List of (chunk_index, path, preset) tuples to cache
            intensity: Processing intensity
            file_signature: File signature (#5251) these chunks were
                produced from — see CachedChunk.file_signature.

        Returns:
            Number of chunks loaded into Tier 1
        """
        async with self._lock:
            loaded_count = 0

            for chunk_idx, chunk_path, preset in chunk_paths:
                chunk = CachedChunk(
                    track_id=track_id,
                    chunk_idx=chunk_idx,
                    preset=preset,
                    intensity=intensity,
                    chunk_path=chunk_path,
                    file_signature=file_signature
                )

                cache_key = chunk.key()

                # Add to Tier 1
                # Check size limit first
                if len(self.tier1_cache) >= TIER1_MAX_CHUNKS * 2:  # × 2 for original + processed
                    await self._evict_tier1_lru()

                self.tier1_cache[cache_key] = chunk
                loaded_count += 1

            if loaded_count > 0:
                logger.info(f"✅ Tier 1 warmed: {loaded_count} chunks for track {track_id}")

            return loaded_count
