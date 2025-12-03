# -*- coding: utf-8 -*-

"""
Cached Audio Fingerprint Analyzer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Wraps AudioFingerprintAnalyzer with LRU fingerprint caching to avoid redundant
expensive 25D fingerprint analysis on repeated files.

Fingerprints are immutable per audio file (for fixed content), so caching them
provides significant speedup: 500-1000ms savings per cache hit.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import hashlib
import logging
from typing import Dict, Optional, Literal
from collections import OrderedDict
from pathlib import Path

from .audio_fingerprint_analyzer import AudioFingerprintAnalyzer
from .persistent_cache import PersistentFingerprintCache

logger = logging.getLogger(__name__)


class CachedAudioFingerprintAnalyzer:
    """
    Fingerprint analyzer with LRU caching.

    Caches the last N fingerprints (immutable per file) to avoid redundant
    expensive 25D fingerprint analysis.

    Performance Impact:
    - Cache miss: ~500-1000ms (full fingerprint analysis)
    - Cache hit: ~0-5ms (dict lookup)
    - Break-even: Cache every 2+ analyses of same file

    Cache Strategy:
    - LRU (Least Recently Used) eviction
    - Cache key: Hash of audio content (first 10KB sample + length)
    - Bounded to 50 fingerprints max (~1-2MB memory)
    """

    def __init__(
        self,
        fingerprint_strategy: Literal["full-track", "sampling"] = "sampling",
        sampling_interval: float = 20.0,
        max_cache_size: int = 50,
        use_persistent_cache: bool = True,
        persistent_cache_path: Optional[Path] = None,
        persistent_cache_max_gb: float = 2.0,
    ):
        """
        Initialize cached fingerprint analyzer with optional persistent cache.

        Args:
            fingerprint_strategy: "full-track" or "sampling"
            sampling_interval: Interval between chunk starts in seconds
            max_cache_size: Maximum number of in-memory cached fingerprints
            use_persistent_cache: Enable SQLite persistent cache (cross-session)
            persistent_cache_path: Path to SQLite database (default: ~/.auralis/cache/fingerprints.db)
            persistent_cache_max_gb: Maximum persistent cache size in GB (default: 2GB)
        """
        self.analyzer = AudioFingerprintAnalyzer(fingerprint_strategy, sampling_interval)
        self.max_cache_size = max_cache_size
        self.cache: OrderedDict[str, Dict[str, float]] = OrderedDict()
        self.cache_hits = 0
        self.cache_misses = 0

        # Initialize persistent cache if enabled
        self.use_persistent_cache = use_persistent_cache
        self.persistent_cache: Optional[PersistentFingerprintCache] = None
        if use_persistent_cache:
            try:
                self.persistent_cache = PersistentFingerprintCache(
                    db_path=persistent_cache_path,
                    max_size_gb=persistent_cache_max_gb,
                )
                logger.debug(f"Persistent fingerprint cache enabled ({persistent_cache_max_gb}GB)")
            except Exception as e:
                logger.warning(f"Could not initialize persistent cache: {e}")
                self.persistent_cache = None

        logger.debug(
            f"CachedAudioFingerprintAnalyzer initialized "
            f"(strategy={fingerprint_strategy}, max_cache={max_cache_size}, "
            f"persistent={'enabled' if self.persistent_cache else 'disabled'})"
        )

    def _compute_cache_key(self, audio: np.ndarray) -> str:
        """
        Compute cache key from audio content.

        Uses a hash of:
        - First 10KB of audio (captures content characteristics)
        - Total audio length (ensures different files don't collide)
        - Sample rate (implicit in audio length)

        Args:
            audio: Audio array

        Returns:
            Cache key string
        """
        # Hash first 10KB of audio data (captures content fingerprint)
        sample_bytes = min(10240, audio.nbytes)  # 10KB or less
        audio_bytes = audio.astype(np.float32).tobytes()[:sample_bytes]

        # Also include length for uniqueness
        length_bytes = len(audio).to_bytes(8, byteorder="little")

        # Combine and hash
        combined = audio_bytes + length_bytes
        cache_key = hashlib.sha256(combined).hexdigest()[:16]  # First 16 chars of hash

        return cache_key

    def analyze(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze audio to extract 25D fingerprint, with multi-level caching.

        Checks in this order:
        1. In-memory LRU cache (50 entries, ~1-5ms)
        2. Persistent SQLite cache (2GB, ~5-20ms)
        3. Fresh analysis (500-1000ms)

        Args:
            audio: Audio signal (stereo or mono)
            sr: Sample rate

        Returns:
            Dict with 25 fingerprint features
        """
        # Check in-memory cache first
        cache_key = self._compute_cache_key(audio)

        if cache_key in self.cache:
            # Memory cache hit: Move to end (LRU) and return
            self.cache.move_to_end(cache_key)
            self.cache_hits += 1
            logger.debug(
                f"Fingerprint memory cache hit (hits: {self.cache_hits}, misses: {self.cache_misses})"
            )
            return self.cache[cache_key]

        # Check persistent cache
        if self.persistent_cache:
            try:
                audio_bytes = audio.astype(np.float32).tobytes()
                fingerprint = self.persistent_cache.get(audio_bytes)
                if fingerprint:
                    # Store in memory cache as well
                    self.cache[cache_key] = fingerprint
                    self.cache_hits += 1
                    logger.debug(
                        f"Fingerprint persistent cache hit "
                        f"(hits: {self.cache_hits}, misses: {self.cache_misses})"
                    )
                    return fingerprint
            except Exception as e:
                logger.debug(f"Error checking persistent cache: {e}")

        # Cache miss: Analyze and store in both caches
        self.cache_misses += 1
        fingerprint = self.analyzer.analyze(audio, sr)

        # Store in memory cache
        self.cache[cache_key] = fingerprint

        # Evict oldest entry if memory cache full (LRU)
        if len(self.cache) > self.max_cache_size:
            evicted_key = next(iter(self.cache))  # First key (oldest)
            del self.cache[evicted_key]
            logger.debug(
                f"Fingerprint memory cache evicted oldest entry "
                f"(cache size: {len(self.cache)}/{self.max_cache_size})"
            )

        # Store in persistent cache
        if self.persistent_cache:
            try:
                audio_bytes = audio.astype(np.float32).tobytes()
                audio_length = len(audio)
                self.persistent_cache.set(audio_bytes, fingerprint, audio_length)
            except Exception as e:
                logger.debug(f"Error storing in persistent cache: {e}")

        logger.debug(
            f"Fingerprint analysis complete (hits: {self.cache_hits}, misses: {self.cache_misses}, "
            f"memory cache size: {len(self.cache)}/{self.max_cache_size})"
        )

        return fingerprint

    def get_cache_stats(self) -> Dict[str, any]:
        """Get cache statistics for monitoring."""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (
            (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        )

        stats = {
            "memory_hits": self.cache_hits,
            "memory_misses": self.cache_misses,
            "hit_rate_percent": hit_rate,
            "memory_cache_size": len(self.cache),
            "memory_cache_max": self.max_cache_size,
        }

        # Add persistent cache stats if available
        if self.persistent_cache:
            persistent_stats = self.persistent_cache.get_stats()
            stats.update(
                {
                    "persistent_entries": persistent_stats.get("total_entries", 0),
                    "persistent_size_mb": persistent_stats.get("total_size_mb", 0),
                    "persistent_db_size_mb": persistent_stats.get("db_size_mb", 0),
                    "persistent_max_gb": persistent_stats.get("max_size_gb", 0),
                    "persistent_hits": persistent_stats.get("hits", 0),
                    "persistent_misses": persistent_stats.get("misses", 0),
                }
            )

        return stats

    def clear_cache(self):
        """Clear all cached fingerprints (memory and persistent)."""
        self.cache.clear()
        if self.persistent_cache:
            self.persistent_cache.clear()
        logger.debug("Fingerprint cache cleared (memory and persistent)")


# Convenience function for backward compatibility
def create_cached_fingerprint_analyzer(
    fingerprint_strategy: Literal["full-track", "sampling"] = "sampling",
    sampling_interval: float = 20.0,
    max_cache_size: int = 50,
) -> CachedAudioFingerprintAnalyzer:
    """
    Factory function to create cached fingerprint analyzer.

    Args:
        fingerprint_strategy: "full-track" or "sampling"
        sampling_interval: Interval between chunk starts in seconds
        max_cache_size: Maximum number of cached fingerprints

    Returns:
        CachedAudioFingerprintAnalyzer instance
    """
    return CachedAudioFingerprintAnalyzer(
        fingerprint_strategy, sampling_interval, max_cache_size
    )
