"""
Streamlined Cache Manager for Auralis Beta.9
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two-tier caching strategy:
- Tier 1 (Hot): Current + next chunk for instant playback and toggle (12 MB)
- Tier 2 (Warm): Full track cache for instant seeking and navigation (60-120 MB)

Replaces the complex multi-tier buffer system (1,459 lines) with a simple,
predictable caching strategy (~150 lines).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Configuration
# NEW (Beta 12.1): 15s chunks with 10s intervals = 5s overlap for natural crossfades
CHUNK_DURATION = 15.0  # seconds per chunk (actual chunk length)
CHUNK_INTERVAL = 10.0   # seconds between chunk starts (playback interval)
CHUNK_SIZE_MB = 1.5    # estimated size per chunk (stereo 44.1kHz, float32) - increased from 1.0 for 15s chunks

# Tier 1: Hot cache (current + next chunk)
TIER1_MAX_CHUNKS = 2   # Current + next
TIER1_MAX_SIZE_MB = TIER1_MAX_CHUNKS * CHUNK_SIZE_MB * 2  # × 2 for original + processed = 4 MB

# Tier 2: Warm cache (full track)
TIER2_MAX_TRACKS = 2   # Keep last 2 tracks fully cached
TIER2_MAX_SIZE_MB = 240  # Max 240 MB total (2 tracks × 60 MB each average)


@dataclass
class CachedChunk:
    """Represents a cached audio chunk."""
    track_id: int
    chunk_idx: int
    preset: Optional[str]  # None for original, preset name for processed
    intensity: float
    chunk_path: Path
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)

    def key(self) -> str:
        """Generate unique cache key."""
        preset_key = "original" if self.preset is None else self.preset
        return f"{self.track_id}_{preset_key}_{self.intensity:.1f}_{self.chunk_idx}"

    def is_original(self) -> bool:
        """Check if this is an original (unprocessed) chunk."""
        return self.preset is None

    def mark_accessed(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_access = time.time()


@dataclass
class TrackCacheStatus:
    """Track-level cache status."""
    track_id: int
    total_chunks: int
    cached_chunks_original: Set[int] = field(default_factory=set)
    cached_chunks_processed: Set[int] = field(default_factory=set)
    cache_complete: bool = False
    cache_start_time: float = field(default_factory=time.time)

    def get_completion_percent(self) -> float:
        """Get cache completion percentage for processed chunks."""
        if self.total_chunks == 0:
            return 0.0
        return (len(self.cached_chunks_processed) / self.total_chunks) * 100

    def is_fully_cached(self) -> bool:
        """Check if track is fully cached (both original and processed)."""
        return (len(self.cached_chunks_original) == self.total_chunks and
                len(self.cached_chunks_processed) == self.total_chunks)


class StreamlinedCacheManager:
    """
    Simplified two-tier cache manager for predictable audio streaming.

    Tier 1 (Hot): Current + next chunk (12 MB)
    - Instant playback continuity
    - Instant auto-mastering toggle
    - Always active

    Tier 2 (Warm): Full track cache (60-120 MB per track)
    - Instant seeking anywhere in track
    - Instant previous track navigation
    - Built in background while playing
    - LRU eviction (keep last 2 tracks)
    """

    def __init__(self) -> None:
        # Cache storage: key -> CachedChunk
        self.tier1_cache: Dict[str, CachedChunk] = {}
        self.tier2_cache: Dict[str, CachedChunk] = {}

        # Track cache status
        self.track_status: Dict[int, TrackCacheStatus] = {}

        # NEW (Priority 4): Mastering recommendations cache
        # Maps track_id -> serialized MasteringRecommendation dict
        self.mastering_recommendations: Dict[int, Dict[str, Any]] = {}

        # Playback state
        self.current_track_id: Optional[int] = None
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

        logger.info("StreamlinedCacheManager initialized (12 MB Tier 1)")

    def _get_current_chunk(self, position: float) -> int:
        """Calculate chunk index from playback position.
        Uses CHUNK_INTERVAL (10s) since chunks start every 10s."""
        return int(position // CHUNK_INTERVAL)

    def _calculate_total_chunks(self, duration: float) -> int:
        """Calculate total chunks needed for track.
        Uses CHUNK_INTERVAL (10s) since chunks start every 10s."""
        return int(duration // CHUNK_INTERVAL) + (1 if duration % CHUNK_INTERVAL > 0 else 0)

    async def update_position(
        self,
        track_id: int,
        position: float,
        preset: str = "adaptive",
        intensity: float = 1.0,
        track_duration: Optional[float] = None
    ) -> None:
        """
        Update current playback position.

        Args:
            track_id: Current track ID
            position: Position in seconds
            preset: Current preset
            intensity: Processing intensity
            track_duration: Total track duration (for cache planning)
        """
        async with self._lock:
            track_changed = track_id != self.current_track_id
            preset_changed = preset != self.current_preset

            # Update state
            self.current_track_id = track_id
            self.current_position = position
            self.current_preset = preset
            self.intensity = intensity

            # Initialize track status if new track
            if track_changed and track_duration:
                total_chunks = self._calculate_total_chunks(track_duration)
                self.track_status[track_id] = TrackCacheStatus(
                    track_id=track_id,
                    total_chunks=total_chunks
                )
                logger.info(f"Track {track_id}: {total_chunks} chunks needed ({track_duration:.1f}s)")

            # Clear old Tier 1 cache on track change
            if track_changed:
                await self._clear_tier1_cache()
                logger.info(f"Track changed: {self.current_track_id} -> {track_id}, cleared Tier 1")

            # Clear old Tier 2 cache on preset change (need to recache processed chunks)
            if preset_changed and track_id in self.track_status:
                await self._clear_tier2_processed_chunks(track_id)
                logger.info(f"Preset changed: {self.current_preset} -> {preset}, cleared processed chunks")

    async def get_chunk(
        self,
        track_id: int,
        chunk_idx: int,
        preset: Optional[str] = None,
        intensity: float = 1.0
    ) -> Tuple[Optional[Path], str]:
        """
        Get chunk from cache.

        Args:
            track_id: Track ID
            chunk_idx: Chunk index
            preset: Preset (None for original)
            intensity: Processing intensity

        Returns:
            (chunk_path, tier) - tier is "tier1", "tier2", or "miss"
        """
        preset_key = "original" if preset is None else preset
        cache_key = f"{track_id}_{preset_key}_{intensity:.1f}_{chunk_idx}"

        # Check Tier 1 first (hot)
        if cache_key in self.tier1_cache:
            chunk = self.tier1_cache[cache_key]
            chunk.mark_accessed()
            self.tier1_hits += 1
            logger.debug(f"Tier 1 HIT: {cache_key}")
            return chunk.chunk_path, "tier1"

        # Check Tier 2 (warm)
        if cache_key in self.tier2_cache:
            chunk = self.tier2_cache[cache_key]
            chunk.mark_accessed()
            self.tier2_hits += 1
            logger.debug(f"Tier 2 HIT: {cache_key}")
            return chunk.chunk_path, "tier2"

        # Cache miss - always increment tier1_misses (total misses)
        self.tier1_misses += 1
        logger.debug(f"Cache MISS: {cache_key}")
        return None, "miss"

    async def add_chunk(
        self,
        track_id: int,
        chunk_idx: int,
        chunk_path: Path,
        preset: Optional[str] = None,
        intensity: float = 1.0,
        tier: str = "auto"
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

        Returns:
            True if added successfully
        """
        async with self._lock:
            chunk = CachedChunk(
                track_id=track_id,
                chunk_idx=chunk_idx,
                preset=preset,
                intensity=intensity,
                chunk_path=chunk_path
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
                # Check Tier 2 size limit
                tier2_size_mb = len(self.tier2_cache) * CHUNK_SIZE_MB
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
        """Evict least recently used track from Tier 2."""
        if not self.tier2_cache:
            return

        # Find oldest track
        track_ids = set(chunk.track_id for chunk in self.tier2_cache.values())
        if not track_ids:
            return

        # Keep current and previous track
        protected_tracks = {self.current_track_id}
        track_ages = {
            tid: min(chunk.last_access for chunk in self.tier2_cache.values()
                    if chunk.track_id == tid)
            for tid in track_ids if tid not in protected_tracks
        }

        if not track_ages:
            return

        # Evict oldest track
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

    def get_track_cache_status(self, track_id: int) -> Optional[TrackCacheStatus]:
        """Get cache status for a track."""
        return self.track_status.get(track_id)

    def is_track_fully_cached(self, track_id: int) -> bool:
        """Check if track is fully cached in Tier 2."""
        status = self.track_status.get(track_id)
        return status.cache_complete if status else False

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        tier1_size_mb = len(self.tier1_cache) * CHUNK_SIZE_MB
        tier2_size_mb = len(self.tier2_cache) * CHUNK_SIZE_MB

        total_requests = (self.tier1_hits + self.tier1_misses +
                         self.tier2_hits + self.tier2_misses)

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
                "hit_rate": self.tier2_hits / max(1, total_requests) if total_requests > 0 else 0.0,
                "tracks_cached": len(set(c.track_id for c in self.tier2_cache.values()))
            },
            "overall": {
                "total_chunks": len(self.tier1_cache) + len(self.tier2_cache),
                "total_size_mb": tier1_size_mb + tier2_size_mb,
                "total_hits": self.tier1_hits + self.tier2_hits,
                "total_misses": self.tier1_misses + self.tier2_misses,
                "overall_hit_rate": (self.tier1_hits + self.tier2_hits) / max(1, total_requests)
            },
            "tracks": {
                track_id: {
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
        chunk_paths: List[Tuple[int, Path, Optional[str]]],
        intensity: float = 1.0
    ) -> int:
        """
        Immediately warm Tier 1 cache with pre-processed chunks.

        This proactively loads the current and next chunks into Tier 1 cache
        to ensure instant playback continuity and fast preset switching.

        Args:
            track_id: Track ID
            chunk_paths: List of (chunk_index, path, preset) tuples to cache
            intensity: Processing intensity

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
                    chunk_path=chunk_path
                )

                cache_key = chunk.key()

                # Add to Tier 1
                # Check size limit first
                if len(self.tier1_cache) >= TIER1_MAX_CHUNKS * 2:  # × 2 for original + processed
                    await self._evict_tier1_lru()

                self.tier1_cache[cache_key] = chunk
                loaded_count += 1

            if loaded_count > 0:
                preset_str = "original/processed" if len(chunk_paths) > 1 else "original"
                logger.info(f"✅ Tier 1 warmed: {loaded_count} chunks for track {track_id}")

            return loaded_count

    def set_mastering_recommendation(self, track_id: int, recommendation: Dict[str, Any]) -> None:
        """
        Cache a mastering recommendation for a track (Priority 4).

        Args:
            track_id: Track database ID
            recommendation: Serialized MasteringRecommendation dict from adaptive_mastering_engine.recommend_weighted()
        """
        self.mastering_recommendations[track_id] = recommendation
        logger.info(
            f"📊 Cached mastering recommendation for track {track_id}: "
            f"{recommendation.get('primary_profile_name', 'unknown')}, "
            f"confidence={recommendation.get('confidence_score', 0):.0%}, "
            f"blended={'yes' if recommendation.get('weighted_profiles') else 'no'}"
        )

    def get_mastering_recommendation(self, track_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached mastering recommendation for a track (Priority 4).

        Args:
            track_id: Track database ID

        Returns:
            Serialized MasteringRecommendation dict or None if not cached
        """
        return self.mastering_recommendations.get(track_id)

    def clear_mastering_recommendations(self) -> None:
        """Clear all cached mastering recommendations."""
        self.mastering_recommendations.clear()
        logger.info("Cleared all mastering recommendations from cache")

    async def clear_all(self) -> None:
        """Clear all caches."""
        async with self._lock:
            self.tier1_cache.clear()
            self.tier2_cache.clear()
            self.track_status.clear()
            self.mastering_recommendations.clear()
            logger.info("All caches cleared")


# Global instance
streamlined_cache_manager = StreamlinedCacheManager()
