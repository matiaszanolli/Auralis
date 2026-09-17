"""
Streamlined Cache Eviction
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tier sizing and LRU eviction for StreamlinedCacheManager, split out of
cache/manager.py (#5238). Kept apart so the eviction invariants (#4238,
#4793) can be audited in one place.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging

from .models import CachedChunk, TrackCacheStatus

logger = logging.getLogger(__name__)


class CacheEvictionMixin:
    """Tier size accounting and eviction.

    State is initialized by StreamlinedCacheManager.__init__, not here —
    declared here only so type checkers know this mixin depends on it.
    """

    tier1_cache: dict[str, CachedChunk]
    tier2_cache: dict[str, CachedChunk]
    track_status: dict[int, TrackCacheStatus]
    current_track_id: int | None

    @staticmethod
    def _tier_size_mb(cache: dict[str, CachedChunk]) -> float:
        """Real accumulated size of a tier's cached chunks, in MB (#4793).

        Sums each entry's stat()'d size_bytes rather than multiplying chunk
        count by the nominal CHUNK_SIZE_MB estimate, which assumed every
        chunk is CHUNK_DURATION long (true only for chunk 0) and over-counted
        every regular CHUNK_INTERVAL-length chunk by ~50%.
        """
        return sum(chunk.size_bytes for chunk in cache.values()) / (1024 * 1024)

    async def _evict_tier1_lru(self) -> None:
        """Evict least recently used chunk from Tier 1."""
        if not self.tier1_cache:
            return

        # Find LRU entry
        lru_key = min(self.tier1_cache.keys(),
                     key=lambda k: self.tier1_cache[k].last_access)

        del self.tier1_cache[lru_key]
        logger.debug(f"Evicted from Tier 1: {lru_key}")

    async def _evict_tier2_lru(self) -> None:
        """Evict from Tier 2 to bring it back under TIER2_MAX_SIZE_MB.

        Prefers evicting an entire non-current track — that's the "keep the
        current + recent tracks warm" navigation promise. When the current
        track is the ONLY track with Tier 2 entries (the common
        single-track-playing case), there is no other track to evict:
        add_chunk still inserted the new entry regardless, so the budget was
        never actually enforced for a single long track (#4793). Falls back
        to evicting the single least-recently-used chunk within the current
        track instead of no-op'ing.
        """
        if not self.tier2_cache:
            return

        # Find oldest track
        track_ids = {chunk.track_id for chunk in self.tier2_cache.values()}

        # Keep current track
        protected_tracks = {self.current_track_id}
        track_ages = {
            tid: min(chunk.last_access for chunk in self.tier2_cache.values()
                    if chunk.track_id == tid)
            for tid in track_ids if tid not in protected_tracks
        }

        if track_ages:
            # Evict oldest non-current track
            oldest_track = min(track_ages.keys(), key=lambda k: track_ages[k])

            keys_to_remove = [
                k for k, chunk in self.tier2_cache.items()
                if chunk.track_id == oldest_track
            ]

            for key in keys_to_remove:
                del self.tier2_cache[key]

            # Remove from track status
            if oldest_track in self.track_status:
                del self.track_status[oldest_track]

            logger.info(f"Evicted track {oldest_track} from Tier 2 ({len(keys_to_remove)} chunks)")
            return

        # Only the current (protected) track has entries — fall back to
        # per-chunk LRU within it so a single long track's budget is still
        # enforced (#4793) instead of growing without bound.
        lru_key = min(self.tier2_cache.keys(), key=lambda k: self.tier2_cache[k].last_access)
        self._forget_tier2_chunk(self.tier2_cache.pop(lru_key))

        logger.debug(
            f"Evicted chunk from Tier 2 (intra-track LRU, single-track budget): {lru_key}"
        )

    def _forget_tier2_chunk(self, chunk: CachedChunk) -> None:
        """Un-record a removed Tier 2 chunk from its track's status, so the
        track stops reporting itself as fully cached."""
        status = self.track_status.get(chunk.track_id)
        if status is None:
            return
        if chunk.is_original():
            status.cached_chunks_original.discard(chunk.chunk_idx)
        else:
            status.cached_chunks_processed.discard(chunk.chunk_idx)
        status.cache_complete = False

    async def _clear_tier1_cache(self) -> None:
        """Clear entire Tier 1 cache."""
        self.tier1_cache.clear()

    async def _clear_tier2_processed_chunks(self, track_id: int) -> None:
        """Clear processed chunks for a track (keep original)."""
        keys_to_remove = [
            k for k, chunk in self.tier2_cache.items()
            if chunk.track_id == track_id and not chunk.is_original()
        ]

        for key in keys_to_remove:
            del self.tier2_cache[key]

        # Reset processed chunks in status
        if track_id in self.track_status:
            self.track_status[track_id].cached_chunks_processed.clear()
            self.track_status[track_id].cache_complete = False
