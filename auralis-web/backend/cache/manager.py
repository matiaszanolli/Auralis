"""
Streamlined Cache Manager for Auralis Beta.9
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two-tier caching strategy:
- Tier 1 (Hot): Current + next chunk for instant playback and toggle (~10 MB)
- Tier 2 (Warm): Full track cache for instant seeking and navigation (240 MB budget)

Replaces the complex multi-tier buffer system (1,459 lines) with a simple,
predictable caching strategy.

StreamlinedCacheManager keeps chunk lookup and insertion here and composes
the rest from mixins (#5238):

- ``playback_mixin``: playback position and position-to-chunk mapping
- ``eviction_mixin``: tier sizing and LRU eviction
- ``status_mixin``: per-track status, statistics and Tier 1 warming
- ``clearing_mixin``: per-track / full clearing incl. on-disk chunk files
- ``recommendations_mixin``: the mastering recommendation cache

Constants and record types live in ``models`` and are re-exported here.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from config.limits import chunk_cache_dir

# Chunk geometry comes from chunk_boundaries — the single source of truth (#4025)
# — instead of a third local copy that would drift and cause cache-index errors.
# Re-exported (cache/__init__.py forwards these) so callers keep resolving them.
from core.encoding.atomic_io import is_wav_complete
from core.chunk_boundaries import (  # noqa: F401
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    chunk_for_position,
    content_chunk_count,
)

from .clearing_mixin import CacheClearingMixin

# Re-exported: callers and tests import the tier budgets and record types from
# cache.manager, where they lived before #5238.
from .models import (  # noqa: F401
    CHUNK_SIZE_MB,
    RECOMMENDATION_TTL_S,
    TIER1_MAX_CHUNKS,
    TIER1_MAX_SIZE_MB,
    TIER2_MAX_SIZE_MB,
    TIER2_MAX_TRACKS,
    CachedChunk,
    PlaybackSnapshot,
    TrackCacheStatus,
)
from .playback_mixin import CachePlaybackMixin
from .recommendations_mixin import RecommendationCacheMixin
from .status_mixin import CacheStatusMixin

logger = logging.getLogger(__name__)


class StreamlinedCacheManager(
    CachePlaybackMixin,
    CacheStatusMixin,
    CacheClearingMixin,
    RecommendationCacheMixin,
):
    """
    Simplified two-tier cache manager for predictable audio streaming.

    Tier 1 (Hot): Current + next chunk (~10 MB)
    - Instant playback continuity
    - Instant auto-mastering toggle
    - Always active

    Tier 2 (Warm): Full track cache (240 MB budget, real on-disk chunk sizes)
    - Instant seeking anywhere in track
    - Instant previous track navigation
    - Built in background while playing
    - LRU eviction: whole non-current track preferred; falls back to
      per-chunk LRU within the current track when it's the only one present
      (#4793), so a single long track's budget is enforced too. Purely
      size-driven (TIER2_MAX_SIZE_MB) — TIER2_MAX_TRACKS is not a separate
      eviction trigger; see its definition in cache/models.py.
    """

    def __init__(self) -> None:
        # The on-disk chunk directory clear_track() sweeps (#5340). An
        # attribute rather than a per-call lookup so tests can point it at a
        # scratch directory instead of the real shared cache.
        self.chunk_dir: Path = chunk_cache_dir()

        # Cache storage: key -> CachedChunk
        self.tier1_cache: dict[str, CachedChunk] = {}
        self.tier2_cache: dict[str, CachedChunk] = {}

        # Track cache status
        self.track_status: dict[int, TrackCacheStatus] = {}

        # NEW (Priority 4): Mastering recommendations cache.
        # OrderedDict so we can LRU-evict at MAX_RECOMMENDATIONS — prior
        # code used a plain dict and the singleton instance accumulated
        # entries for the entire backend lifetime, growing 1-5 KB per
        # distinct track played (fixes #3555 / BE-NEW-97).
        self.mastering_recommendations: OrderedDict[
            tuple[int, float], tuple[float, dict[str, Any]]
        ] = OrderedDict()
        self.MAX_RECOMMENDATIONS = 256

        # Playback state
        self.current_track_id: int | None = None
        self.current_position: float = 0.0
        self.current_preset: str = "adaptive"
        self.intensity: float = 1.0
        self.auto_mastering_enabled: bool = True

        # Statistics
        self.tier1_hits: int = 0
        self.tier1_misses: int = 0
        self.tier2_hits: int = 0
        self.tier2_misses: int = 0

        # Thread safety
        self._lock: asyncio.Lock = asyncio.Lock()

        logger.info(f"StreamlinedCacheManager initialized ({TIER1_MAX_SIZE_MB:.1f} MB Tier 1)")

    async def get_chunk(
        self,
        track_id: int,
        chunk_idx: int,
        preset: str | None = None,
        intensity: float = 1.0,
        file_signature: str = ""
    ) -> tuple[Path | None, str]:
        """
        Get chunk from cache.

        Args:
            track_id: Track ID
            chunk_idx: Chunk index
            preset: Preset (None for original)
            intensity: Processing intensity
            file_signature: File signature (#5251) the chunk should have been
                cached under — a mismatch (e.g. the file was edited since)
                is a cache miss, not an error, exactly like the on-disk tier.

        Returns:
            (chunk_path, tier) - tier is "tier1", "tier2", or "miss"
        """
        cache_key = CachedChunk.make_key(track_id, chunk_idx, preset, intensity, file_signature)

        # Tier 1 (hot) first, then Tier 2 (warm).
        for tier, cache in (("tier1", self.tier1_cache), ("tier2", self.tier2_cache)):
            chunk = cache.get(cache_key)
            if chunk is None:
                continue
            # #5493: the bytes live in a directory that ChunkCacheManager's
            # process-wide reaper also sweeps, with no knowledge of these
            # dicts — verify before serving, as ChunkCacheManager does.
            if not await asyncio.to_thread(is_wav_complete, chunk.chunk_path):
                await self._drop_stale_chunk(tier, cache_key, chunk)
                continue
            chunk.mark_accessed()
            if tier == "tier1":
                self.tier1_hits += 1
            else:
                self.tier2_hits += 1
            logger.debug(f"{tier} HIT: {cache_key}")
            return chunk.chunk_path, tier

        # Both tiers were checked and missed. Each tier exposes its own miss
        # counter, while the overall stats below count this request once.
        self.tier1_misses += 1
        self.tier2_misses += 1
        logger.debug(f"Cache MISS: {cache_key}")
        return None, "miss"

    async def _drop_stale_chunk(self, tier: str, cache_key: str, chunk: CachedChunk) -> None:
        """Evict an entry whose file is gone or truncated (#5493)."""
        async with self._lock:
            cache = self.tier1_cache if tier == "tier1" else self.tier2_cache
            # Identity check: a concurrent add_chunk may have replaced it.
            if cache.get(cache_key) is not chunk:
                return
            del cache[cache_key]
            if tier == "tier2":
                self._forget_tier2_chunk(chunk)
        logger.warning(f"{tier} entry {cache_key} lost its file on disk; evicted")

    async def add_chunk(
        self,
        track_id: int,
        chunk_idx: int,
        chunk_path: Path,
        preset: str | None = None,
        intensity: float = 1.0,
        tier: str = "auto",
        file_signature: str = ""
    ) -> bool:
        """
        Add chunk to cache.

        Args:
            track_id: Track ID
            chunk_idx: Chunk index
            chunk_path: Path to cached chunk file
            preset: Preset (None for original)
            intensity: Processing intensity
            tier: "tier1", "tier2", or "auto" (auto-detect)
            file_signature: File signature (#5251) this chunk was produced
                from — carried through to the cache key so an in-place file
                edit produces a fresh key rather than overwriting/serving a
                stale one.

        Returns:
            True if added successfully
        """
        async with self._lock:
            chunk = CachedChunk(
                track_id=track_id,
                chunk_idx=chunk_idx,
                preset=preset,
                intensity=intensity,
                chunk_path=chunk_path,
                file_signature=file_signature
            )

            cache_key = chunk.key()

            # Auto-detect tier if not specified
            if tier == "auto":
                current_chunk = self._get_current_chunk(self.current_position)
                # Tier 1: Current or next chunk
                if chunk_idx in [current_chunk, current_chunk + 1]:
                    tier = "tier1"
                else:
                    tier = "tier2"

            # Add to appropriate tier
            if tier == "tier1":
                # Check Tier 1 size limit
                if len(self.tier1_cache) >= TIER1_MAX_CHUNKS * 2:  # × 2 for original + processed
                    await self._evict_tier1_lru()

                self.tier1_cache[cache_key] = chunk
                logger.debug(f"Added to Tier 1: {cache_key}")

            else:  # tier2
                # Check Tier 2 size limit against real on-disk sizes (#4793)
                tier2_size_mb = self._tier_size_mb(self.tier2_cache)
                if tier2_size_mb >= TIER2_MAX_SIZE_MB:
                    await self._evict_tier2_lru()

                self.tier2_cache[cache_key] = chunk
                logger.debug(f"Added to Tier 2: {cache_key}")

                # Update track status
                if track_id in self.track_status:
                    if preset is None:
                        self.track_status[track_id].cached_chunks_original.add(chunk_idx)
                    else:
                        self.track_status[track_id].cached_chunks_processed.add(chunk_idx)

                    # Check if track is fully cached
                    if self.track_status[track_id].is_fully_cached():
                        self.track_status[track_id].cache_complete = True
                        cache_time = time.time() - self.track_status[track_id].cache_start_time
                        logger.info(f"✅ Track {track_id} fully cached in {cache_time:.1f}s")

            return True


# Global instance
streamlined_cache_manager = StreamlinedCacheManager()
