"""
Streamlined Cache Manager for Auralis Beta.9
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two-tier caching strategy:
- Tier 1 (Hot): Current + next chunk for instant playback and toggle (~10 MB)
- Tier 2 (Warm): Full track cache for instant seeking and navigation (240 MB budget)

Replaces the complex multi-tier buffer system (1,459 lines) with a simple,
predictable caching strategy (~150 lines).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

# Chunk geometry comes from chunk_boundaries — the single source of truth (#4025)
# — instead of a third local copy that would drift and cause cache-index errors.
# Re-exported (cache/__init__.py forwards these) so callers keep resolving them.
from core.chunk_boundaries import (  # noqa: F401
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    chunk_for_position,
    content_chunk_count,
)

logger = logging.getLogger(__name__)

# Configuration
#
# Nominal per-chunk size estimate used only for tier-size eviction accounting
# (CachedChunk stores a Path, not raw bytes, so there is no in-memory buffer
# to measure directly). Cached chunks are persisted as 16-bit PCM WAV — see
# WAVEncoder(default_subtype='PCM_16') / encode_to_wav() in
# core/chunked_processor.py — NOT float32. The previous 1.5 MB literal
# assumed float32 (4 bytes/sample) math and was ~3.4x too low relative to the
# real ~2.5 MB PCM_16 chunk size at the nominal 44.1kHz stereo baseline,
# letting actual disk usage run well past the documented tier budgets before
# the size-based eviction check believed it was over budget (fixes #4238).
_NOMINAL_SAMPLE_RATE = 44100
_NOMINAL_CHANNELS = 2
_PCM16_BYTES_PER_SAMPLE = 2
CHUNK_SIZE_MB = (
    _NOMINAL_CHANNELS * _NOMINAL_SAMPLE_RATE * CHUNK_DURATION * _PCM16_BYTES_PER_SAMPLE
) / (1024 * 1024)

# Tier 1: Hot cache (current + next chunk)
TIER1_MAX_CHUNKS = 2   # Current + next
TIER1_MAX_SIZE_MB = TIER1_MAX_CHUNKS * CHUNK_SIZE_MB * 2  # × 2 for original + processed (~10 MB)

# Tier 2: Warm cache (full track)
# NOTE (#4793 sibling, not fixed here): eviction is purely size-driven
# (TIER2_MAX_SIZE_MB via _evict_tier2_lru) — this constant is exported but
# never read, so the "keep last 2 tracks" count-based policy the class
# docstring advertises isn't actually implemented. However many tracks fit
# in the 240 MB budget stay cached; a 3rd track is not specifically evicted
# just for being a 3rd track. Flagged as a separate follow-up.
TIER2_MAX_TRACKS = 2   # Keep last 2 tracks fully cached
TIER2_MAX_SIZE_MB = 240  # Max 240 MB total (~95 chunks at the corrected CHUNK_SIZE_MB)

# Shared freshness contract for mastering recommendations (#3865/#5280).
RECOMMENDATION_TTL_S = 60.0


@dataclass
class CachedChunk:
    """Represents a cached audio chunk."""
    track_id: int
    chunk_idx: int
    preset: str | None  # None for original, preset name for processed
    intensity: float
    chunk_path: Path
    # File signature (mtime+size hash, see core/file_signature.py) the chunk
    # was cached under (#5251). Every sibling tier already keys on this —
    # SimpleChunkCache (core/chunk_cache.py, CACHE_VERSION 4, #4358) and the
    # on-disk ChunkPathCache/ChunkCacheManager both include it — but this
    # tier, which is consulted BEFORE the signature-aware disk lookup, never
    # got the fix, so an in-place file edit (e.g. a re-master landing at the
    # identical path) kept serving pre-edit audio from here until LRU
    # eviction happened to reclaim the entry. Defaults to "" so a caller that
    # genuinely has no signature available degrades to the old (unsafe but
    # unchanged) behavior rather than erroring.
    file_signature: str = ""
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    # Real on-disk size, stat()'d once at insert time (#4793) rather than the
    # old nominal CHUNK_SIZE_MB-per-chunk estimate, which assumed every chunk
    # is CHUNK_DURATION (15s) long — true only for chunk 0; every regular
    # chunk is CHUNK_INTERVAL (10s), so the estimate over-accounted actual
    # disk usage by ~50%. stat()-ing once here (not on every accounting
    # check) keeps size lookups O(1) after insertion.
    size_bytes: int = 0

    def __post_init__(self) -> None:
        if self.size_bytes == 0:
            try:
                self.size_bytes = self.chunk_path.stat().st_size
            except OSError:
                # Path doesn't exist yet / was already cleaned up — best-effort,
                # matches the rest of this cache's graceful-degradation style.
                self.size_bytes = 0

    @staticmethod
    def make_key(
        track_id: int,
        chunk_idx: int,
        preset: str | None,
        intensity: float,
        file_signature: str = "",
    ) -> str:
        """Compose the cache key — the single source of truth for this tier's
        key format, so a lookup (which has no CachedChunk instance yet) and
        an insert (which does, via .key()) can never drift apart."""
        preset_key = "original" if preset is None else preset
        return f"{track_id}_{preset_key}_{intensity:.1f}_{chunk_idx}_{file_signature}"

    def key(self) -> str:
        """Generate unique cache key."""
        return CachedChunk.make_key(
            self.track_id, self.chunk_idx, self.preset, self.intensity, self.file_signature
        )

    def is_original(self) -> bool:
        """Check if this is an original (unprocessed) chunk."""
        return self.preset is None

    def mark_accessed(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_access = time.time()


class PlaybackSnapshot(NamedTuple):
    """One internally-consistent read of the cache manager's playback state.

    All five values come from a single ``_lock`` acquisition (#4546), so
    consumers can rely on ``chunk_idx`` genuinely belonging to ``track_id``
    rather than being derived from a position that has since moved to a
    different track.
    """
    track_id: int
    position: float
    chunk_idx: int
    preset: str
    intensity: float


@dataclass
class TrackCacheStatus:
    """Track-level cache status."""
    track_id: int
    total_chunks: int
    total_duration: float | None = None
    cached_chunks_original: set[int] = field(default_factory=set)
    cached_chunks_processed: set[int] = field(default_factory=set)
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
      eviction trigger; see its definition above.
    """

    def __init__(self) -> None:
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

    @staticmethod
    def _tier_size_mb(cache: dict[str, CachedChunk]) -> float:
        """Real accumulated size of a tier's cached chunks, in MB (#4793).

        Sums each entry's stat()'d size_bytes rather than multiplying chunk
        count by the nominal CHUNK_SIZE_MB estimate, which assumed every
        chunk is CHUNK_DURATION long (true only for chunk 0) and over-counted
        every regular CHUNK_INTERVAL-length chunk by ~50%.
        """
        return sum(chunk.size_bytes for chunk in cache.values()) / (1024 * 1024)

    def _get_current_chunk(self, position: float) -> int:
        """Calculate chunk index from playback position.

        Uses chunk_for_position() (#4557/#4791) — the mapping onto the chunk
        that actually EMITS this position, not the naive core-timeline
        floor-division by CHUNK_INTERVAL, which is off by one for roughly
        the first half of every emitted chunk window (every chunk after the
        first is offset by OVERLAP_DURATION from the core timeline; see
        chunk_boundaries.emitted_chunk_start).
        """
        total_chunks = 1
        status = self.track_status.get(self.current_track_id) if self.current_track_id else None
        if status is not None:
            total_chunks = status.total_chunks
        return chunk_for_position(
            position,
            total_chunks,
            total_duration=status.total_duration if status is not None else None,
        )[0]

    def _calculate_total_chunks(self, duration: float) -> int:
        """Content-carrying chunk count — delegates to the chunk-model SoT.

        The cache-completion target must equal ``ChunkedAudioProcessor.
        total_chunks``, which is itself set from ``content_chunk_count()``, so
        this delegates rather than re-deriving the formula (#4620). The naive
        ``ceil(duration / CHUNK_INTERVAL)`` over-counted a 0-content trailing
        chunk for durations in ``(n*INTERVAL, n*INTERVAL + OVERLAP)`` (#4124);
        that fix now lives in exactly one place.
        """
        return content_chunk_count(duration)

    async def get_playback_snapshot(self) -> "PlaybackSnapshot | None":
        """Read the four playback fields in one critical section (#4546).

        ``update_position`` writes ``current_track_id``, ``current_position``,
        ``current_preset`` and ``intensity`` together under ``_lock``. Readers
        that fetch them as four separate awaited/unsynchronised reads can
        observe a mix of generations — e.g. track A's id paired with track B's
        position, yielding a chunk index past A's end. Mirrors
        ``AudioFileManager.get_state_snapshot()`` (#3474), which exists for
        exactly this hazard on the player side.

        Returns ``None`` when no track is playing, preserving the
        ``if not current_track_id: return`` guard callers had before.
        """
        async with self._lock:
            if not self.current_track_id:
                return None
            return PlaybackSnapshot(
                track_id=self.current_track_id,
                position=self.current_position,
                chunk_idx=self._get_current_chunk(self.current_position),
                preset=self.current_preset,
                intensity=self.intensity,
            )

    async def update_position(
        self,
        track_id: int,
        position: float,
        preset: str = "adaptive",
        intensity: float = 1.0,
        track_duration: float | None = None
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
            # Captured before the write so the change log below reports the
            # real transition; it previously read the already-updated fields
            # and always printed "X -> X".
            previous_track_id = self.current_track_id
            previous_preset = self.current_preset

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
                    total_chunks=total_chunks,
                    total_duration=track_duration,
                )
                logger.info(f"Track {track_id}: {total_chunks} chunks needed ({track_duration:.1f}s)")

            # Clear old Tier 1 cache on track change
            if track_changed:
                await self._clear_tier1_cache()
                logger.info(f"Track changed: {previous_track_id} -> {track_id}, cleared Tier 1")

            # Clear old Tier 2 cache on preset change (need to recache processed chunks)
            if preset_changed and track_id in self.track_status:
                await self._clear_tier2_processed_chunks(track_id)
                logger.info(f"Preset changed: {previous_preset} -> {preset}, cleared processed chunks")

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

        # Both tiers were checked and missed. Each tier exposes its own miss
        # counter, while the overall stats below count this request once.
        self.tier1_misses += 1
        self.tier2_misses += 1
        logger.debug(f"Cache MISS: {cache_key}")
        return None, "miss"

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
        evicted = self.tier2_cache.pop(lru_key)

        status = self.track_status.get(evicted.track_id)
        if status is not None:
            if evicted.is_original():
                status.cached_chunks_original.discard(evicted.chunk_idx)
            else:
                status.cached_chunks_processed.discard(evicted.chunk_idx)
            status.cache_complete = False

        logger.debug(
            f"Evicted chunk from Tier 2 (intra-track LRU, single-track budget): {lru_key}"
        )

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
                "original/processed" if len(chunk_paths) > 1 else "original"
                logger.info(f"✅ Tier 1 warmed: {loaded_count} chunks for track {track_id}")

            return loaded_count

    def set_mastering_recommendation(
        self,
        track_id: int,
        recommendation: dict[str, Any],
        confidence_threshold: float = 0.4,
    ) -> None:
        """
        Cache a mastering recommendation for a track (Priority 4).

        LRU-bounded at MAX_RECOMMENDATIONS to prevent unbounded growth in
        the module-level singleton (#3555 / BE-NEW-97).

        Args:
            track_id: Track database ID
            recommendation: Serialized MasteringRecommendation dict from adaptive_mastering_engine.recommend_weighted()
            confidence_threshold: Analysis threshold used to produce the result
        """
        now = time.monotonic()
        stale_keys = [
            key
            for key, (expiry, _) in self.mastering_recommendations.items()
            if expiry <= now
        ]
        for stale_key in stale_keys:
            del self.mastering_recommendations[stale_key]

        cache_key = (track_id, confidence_threshold)
        self.mastering_recommendations[cache_key] = (
            now + RECOMMENDATION_TTL_S,
            recommendation,
        )
        self.mastering_recommendations.move_to_end(cache_key)
        while len(self.mastering_recommendations) > self.MAX_RECOMMENDATIONS:
            self.mastering_recommendations.popitem(last=False)
        logger.info(
            f"📊 Cached mastering recommendation for track {track_id}: "
            f"{recommendation.get('primary_profile_name', 'unknown')}, "
            f"confidence={recommendation.get('confidence_score', 0):.0%}, "
            f"blended={'yes' if recommendation.get('weighted_profiles') else 'no'}"
        )

    def get_mastering_recommendation(
        self, track_id: int, confidence_threshold: float = 0.4
    ) -> dict[str, Any] | None:
        """
        Retrieve cached mastering recommendation for a track (Priority 4).

        Args:
            track_id: Track database ID
            confidence_threshold: Analysis threshold for the cached result

        Returns:
            Serialized MasteringRecommendation dict or None if not cached
        """
        cache_key = (track_id, confidence_threshold)
        cached = self.mastering_recommendations.get(cache_key)
        if cached is None:
            return None

        expiry, recommendation = cached
        if time.monotonic() >= expiry:
            del self.mastering_recommendations[cache_key]
            return None

        self.mastering_recommendations.move_to_end(cache_key)
        return recommendation

    def clear_mastering_recommendations(self) -> None:
        """Clear all cached mastering recommendations."""
        self.mastering_recommendations.clear()
        logger.info("Cleared all mastering recommendations from cache")

    async def clear_track(self, track_id: int) -> int:
        """Clear all cached data for a single track.

        Also deletes the underlying on-disk WAV chunk files (#5249) —
        clearing only the tier1/tier2 in-memory bookkeeping left
        ChunkPathCache's independent on-disk existence check
        (core/chunk_path_cache.py) still finding and serving the exact same
        bytes on the very next request, making the user's "clear and retry"
        troubleshooting lever a no-op for anything already on disk.

        Returns the number of cache entries removed.
        """
        async with self._lock:
            # Remove Tier 1 entries for this track
            t1_removed = [
                (k, v) for k, v in self.tier1_cache.items()
                if v.track_id == track_id
            ]
            for key, _ in t1_removed:
                del self.tier1_cache[key]

            # Remove Tier 2 entries for this track
            t2_removed = [
                (k, v) for k, v in self.tier2_cache.items()
                if v.track_id == track_id
            ]
            for key, _ in t2_removed:
                del self.tier2_cache[key]

            # Remove track status
            self.track_status.pop(track_id, None)

            removed = len(t1_removed) + len(t2_removed)
            chunk_paths = [chunk.chunk_path for _, chunk in (*t1_removed, *t2_removed)]

        # Disk I/O outside the lock — a slow or failing deletion must not
        # hold up other cache operations, and the in-memory bookkeeping
        # above is already committed regardless of the disk outcome.
        await asyncio.to_thread(self._unlink_chunk_files, chunk_paths)

        logger.info(f"Cleared cache for track {track_id} ({removed} entries)")
        return removed

    async def clear_all(self) -> None:
        """Clear all caches, including the underlying on-disk WAV chunk
        files (#5249) — see clear_track()'s docstring for why this matters."""
        async with self._lock:
            chunk_paths = [c.chunk_path for c in self.tier1_cache.values()]
            chunk_paths.extend(c.chunk_path for c in self.tier2_cache.values())
            self.tier1_cache.clear()
            self.tier2_cache.clear()
            self.track_status.clear()
            self.mastering_recommendations.clear()

        await asyncio.to_thread(self._unlink_chunk_files, chunk_paths)
        logger.info(f"All caches cleared ({len(chunk_paths)} on-disk chunk file(s) removed)")

    @staticmethod
    def _unlink_chunk_files(chunk_paths: list[Path]) -> None:
        """Best-effort delete of the on-disk WAV files backing cache entries
        that were just dropped from the in-memory dicts. A file that's
        already gone (race with another cleanup pass, or was never
        actually written) is not an error — matches this cache's
        established graceful-degradation style (see
        CachedChunk.__post_init__)."""
        for path in chunk_paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.warning(f"Could not delete cached chunk file {path}: {e}")


# Global instance
streamlined_cache_manager = StreamlinedCacheManager()
