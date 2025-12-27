"""
Track-Level Analysis Cache
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Caches audio analysis results at the track level to avoid redundant processing
across overlapping chunks.

Current problem: With 15-second chunks at 10-second intervals (5-second overlap),
the same audio is analyzed multiple times:
  - Chunk 0: [0-15s]   - analyzes [0-5], [5-10], [10-15]
  - Chunk 1: [10-25s]  - analyzes [10-15] AGAIN, [15-20], [20-25]
  - Chunk 2: [20-35s]  - analyzes [20-25] AGAIN, [25-30], [30-35]

This cache stores analysis results (fingerprint, tempo, genre, mastering targets)
at the track level and reuses them across chunks.

Expected improvements:
  - Tempo detection: 500-1000ms × 8-12 chunks → 1 extract
  - Fingerprint: 200-500ms × 8-12 chunks → 1 extract + memory cache
  - Genre: 30-100ms × 8-12 chunks → 1 classification
  - Overall: 50-70% speedup per playback

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class TrackAnalysisCache:
    """
    In-memory cache for track-level analysis results.

    Stores:
    - 25D fingerprint (most expensive to compute)
    - Tempo detection (500-1000ms per track)
    - Genre classification (30-100ms per track)
    - Content analysis profile
    - Mastering targets (derived from fingerprint)

    Key design:
    - Per-track cache (one entry per track ID)
    - LRU eviction (keep recent tracks in memory)
    - TTL support (optional expiration)
    - Null-safety (tracks without analysis marked explicitly)
    """

    def __init__(self, max_cached_tracks: int = 50, ttl_seconds: Optional[int] = None):
        """
        Initialize track analysis cache.

        Args:
            max_cached_tracks: Maximum number of tracks to keep in memory (LRU eviction)
            ttl_seconds: Time-to-live for cache entries in seconds (None = no expiration)
        """
        self.max_cached_tracks = max_cached_tracks
        self.ttl_seconds = ttl_seconds

        # Track ID → analysis results
        self._cache: Dict[int, Dict[str, Any]] = {}

        # Track ID → last accessed time (for LRU eviction)
        self._access_times: Dict[int, datetime] = {}

        logger.info(
            f"TrackAnalysisCache initialized: "
            f"max_tracks={max_cached_tracks}, ttl={ttl_seconds}s"
        )

    def get(self, track_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached analysis for a track.

        Returns None if:
        - Track not in cache
        - Cache entry has expired (TTL exceeded)

        Updates access time for LRU tracking.

        Args:
            track_id: Track ID to retrieve

        Returns:
            Analysis dictionary or None if not cached/expired
        """
        if track_id not in self._cache:
            return None

        # Check expiration
        if self.ttl_seconds is not None:
            last_access = self._access_times.get(track_id)
            if last_access and datetime.now() - last_access > timedelta(seconds=self.ttl_seconds):
                logger.debug(f"Cache expired for track {track_id}")
                del self._cache[track_id]
                del self._access_times[track_id]
                return None

        # Update access time (for LRU)
        self._access_times[track_id] = datetime.now()

        logger.debug(f"Cache hit for track {track_id}")
        return self._cache[track_id]

    def put(self, track_id: int, analysis: Dict[str, Any]) -> None:
        """
        Store analysis results for a track.

        Performs LRU eviction if cache is full.

        Args:
            track_id: Track ID
            analysis: Analysis dictionary with keys:
                - fingerprint: Dict[str, float] (25D)
                - content_profile: Dict[str, Any]
                - mastering_targets: Dict[str, float]
                - genre: str
                - tempo: float
                - timestamp: datetime
        """
        # Evict LRU entry if cache is full
        if len(self._cache) >= self.max_cached_tracks and track_id not in self._cache:
            self._evict_lru()

        self._cache[track_id] = analysis
        self._access_times[track_id] = datetime.now()

        logger.info(
            f"Cached analysis for track {track_id}: "
            f"fingerprint={'fingerprint' in analysis}, "
            f"mastering_targets={'mastering_targets' in analysis}"
        )

    def has(self, track_id: int) -> bool:
        """
        Check if track analysis is cached (without updating access time).

        Args:
            track_id: Track ID

        Returns:
            True if track has valid cached analysis
        """
        if track_id not in self._cache:
            return False

        # Check expiration
        if self.ttl_seconds is not None:
            last_access = self._access_times.get(track_id)
            if last_access and datetime.now() - last_access > timedelta(seconds=self.ttl_seconds):
                return False

        return True

    def clear(self, track_id: Optional[int] = None) -> None:
        """
        Clear cache entry(ies).

        Args:
            track_id: Specific track to clear, or None to clear entire cache
        """
        if track_id is None:
            self._cache.clear()
            self._access_times.clear()
            logger.info("Cleared entire track analysis cache")
        else:
            if track_id in self._cache:
                del self._cache[track_id]
                del self._access_times[track_id]
                logger.debug(f"Cleared cache for track {track_id}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with:
            - cached_tracks: Number of tracks in cache
            - max_tracks: Maximum cache size
            - memory_estimate_mb: Rough estimate of memory usage
            - fingerprints_cached: Number of cached fingerprints
        """
        total_size = 0
        fingerprint_count = 0

        for analysis in self._cache.values():
            # Estimate size: ~2KB per basic analysis + ~5KB per fingerprint
            total_size += 2048
            if 'fingerprint' in analysis:
                total_size += 5120
                fingerprint_count += 1

        return {
            'cached_tracks': len(self._cache),
            'max_tracks': self.max_cached_tracks,
            'memory_estimate_mb': total_size / (1024 * 1024),
            'fingerprints_cached': fingerprint_count,
            'ttl_seconds': self.ttl_seconds,
        }

    def _evict_lru(self) -> None:
        """
        Evict the least-recently-used entry from cache.

        This ensures cache doesn't grow unbounded.
        """
        if not self._cache:
            return

        # Find track with earliest access time
        lru_track = min(self._access_times.keys(), key=lambda tid: self._access_times[tid])

        del self._cache[lru_track]
        del self._access_times[lru_track]

        logger.debug(f"Evicted LRU track {lru_track} from cache")


# Global cache instance (initialized once)
_track_analysis_cache: Optional[TrackAnalysisCache] = None


def get_track_analysis_cache() -> TrackAnalysisCache:
    """
    Get or create global track analysis cache instance.

    Uses lazy initialization to ensure it's created only when needed.

    Returns:
        Singleton TrackAnalysisCache instance
    """
    global _track_analysis_cache

    if _track_analysis_cache is None:
        _track_analysis_cache = TrackAnalysisCache(
            max_cached_tracks=50,  # Keep 50 tracks in memory
            ttl_seconds=3600  # 1 hour TTL
        )

    return _track_analysis_cache


def init_track_analysis_cache(max_cached_tracks: int = 50, ttl_seconds: Optional[int] = 3600) -> None:
    """
    Initialize or reinitialize the global track analysis cache.

    Call this during application startup to configure cache parameters.

    Args:
        max_cached_tracks: Maximum number of tracks to keep in memory
        ttl_seconds: Time-to-live for cache entries (None = no expiration)
    """
    global _track_analysis_cache

    _track_analysis_cache = TrackAnalysisCache(
        max_cached_tracks=max_cached_tracks,
        ttl_seconds=ttl_seconds
    )

    logger.info(f"Initialized track analysis cache: max={max_cached_tracks}, ttl={ttl_seconds}s")
