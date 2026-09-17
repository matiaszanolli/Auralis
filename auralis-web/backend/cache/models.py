"""
Streamlined Cache Models
~~~~~~~~~~~~~~~~~~~~~~~~

Tier budgets and the record types the streamlined cache stores and reports.
``cache.manager`` re-exports all of them (#5238).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from core.chunk_boundaries import CHUNK_DURATION

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
    # the on-disk ChunkPathCache/ChunkCacheManager include it — but this
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
