#!/usr/bin/env python3

"""
Simple Chunk Cache
~~~~~~~~~~~~~~~~~~

In-memory LRU cache for processed audio chunks, keyed by
(track_id, chunk_idx, preset, intensity). Extracted from
audio_stream_controller.py (#4071).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import hashlib
import logging
import threading
from collections import OrderedDict

import numpy as np

logger = logging.getLogger(__name__)


class SimpleChunkCache:
    """Simple in-memory cache for processed audio chunks."""

    # Cache version - increment when chunk processing logic OR the key schema changes
    # This invalidates all cached chunks when we fix bugs in extraction/processing
    CACHE_VERSION = 4  # v4: key now includes file_signature (#4358); v3: _extract_chunk_segment overlap handling

    def __init__(self, max_chunks: int = 50, max_memory_bytes: int = 512 * 1024 * 1024) -> None:
        """
        Initialize chunk cache.

        Args:
            max_chunks: Maximum number of chunks to keep in memory
            max_memory_bytes: Maximum total memory for cached audio (default 512 MB)
        """
        self.cache: OrderedDict[str, tuple[np.ndarray, int]] = OrderedDict()
        self.max_chunks: int = max_chunks
        self._max_memory_bytes: int = max_memory_bytes
        self._current_bytes: int = 0
        self._lock = threading.Lock()  # Protects cache from concurrent access (fixes #2436)

    def _make_key(
        self, track_id: int, chunk_idx: int, preset: str, intensity: float, file_signature: str = ""
    ) -> str:
        """Generate cache key from parameters.

        file_signature (#4358) is part of the key so an in-session file change
        (re-scan/re-tag) that keeps the same track_id still MISSES — matching
        the on-disk ChunkCacheManager, whose keys already include it. Without
        it, this in-memory layer would keep serving the previously-processed
        samples and their stored sample_rate for the process lifetime, causing
        stale/wrong-speed audio after a replacement file with a different rate.
        """
        # Include CACHE_VERSION to invalidate stale cached chunks when processing logic changes
        key_str = f"v{self.CACHE_VERSION}:{track_id}:{chunk_idx}:{preset}:{intensity:.2f}:{file_signature}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(
        self,
        track_id: int,
        chunk_idx: int,
        preset: str,
        intensity: float,
        *,
        file_signature: str = ""
    ) -> tuple[np.ndarray, int] | None:
        """
        Get chunk from cache.

        Returns:
            Tuple of (audio_samples, sample_rate) or None if not cached
        """
        with self._lock:
            key = self._make_key(track_id, chunk_idx, preset, intensity, file_signature)
            if key in self.cache:
                # Move to end (LRU)
                self.cache.move_to_end(key)
                logger.debug(f"✅ Cache HIT: chunk {chunk_idx}, preset {preset}")
                return self.cache[key]
            return None

    def put(
        self,
        track_id: int,
        chunk_idx: int,
        preset: str,
        intensity: float,
        audio: np.ndarray,
        sample_rate: int,
        *,
        file_signature: str = ""
    ) -> None:
        """Store chunk in cache."""
        with self._lock:
            key = self._make_key(track_id, chunk_idx, preset, intensity, file_signature)

            chunk_bytes = audio.nbytes

            # Account for overwrite first (#3192): drop the existing entry's
            # bytes from the counter and remove it from the dict so the
            # eviction loops below reflect the true post-overwrite state and
            # don't over-evict siblings. Re-insertion at the end of the dict
            # below also restores LRU ordering for the touched key.
            if key in self.cache:
                old_audio, _ = self.cache[key]
                self._current_bytes -= old_audio.nbytes
                del self.cache[key]

            # Evict by count limit
            while len(self.cache) >= self.max_chunks:
                _removed_key, (removed_audio, _) = self.cache.popitem(last=False)
                self._current_bytes -= removed_audio.nbytes

            # Evict by memory limit (#2084)
            while self._current_bytes + chunk_bytes > self._max_memory_bytes and self.cache:
                _removed_key, (removed_audio, _) = self.cache.popitem(last=False)
                self._current_bytes -= removed_audio.nbytes

            self.cache[key] = (audio, sample_rate)
            self._current_bytes += chunk_bytes
            logger.debug(f"✅ Cached chunk {chunk_idx}, preset {preset}, cache size: {len(self.cache)}")

    def clear(self) -> None:
        """Clear all cached chunks."""
        with self._lock:
            self.cache.clear()
            self._current_bytes = 0

    def invalidate_chunk(
        self, track_id: int, chunk_idx: int, preset: str, intensity: float, *, file_signature: str = ""
    ) -> None:
        """Remove a specific chunk from cache after a processing failure.

        Prevents a stale/corrupt cache entry from causing repeated failures on retry.

        Args:
            track_id: Track ID the chunk belongs to
            chunk_idx: Index of the failed chunk
            preset: Processing preset used
            intensity: Processing intensity used
            file_signature: File signature the chunk was cached under (#4358) —
                must match the value passed to put() to target the same entry.
        """
        with self._lock:
            key = self._make_key(track_id, chunk_idx, preset, intensity, file_signature)
            removed = self.cache.pop(key, None)
            if removed is not None:
                # Sibling of #3192: invalidate_chunk previously dropped the
                # entry but never subtracted its bytes from the counter,
                # causing the same drift as the overwrite bug.
                removed_audio, _ = removed
                self._current_bytes -= removed_audio.nbytes
                logger.debug(f"Invalidated stale cache entry: chunk {chunk_idx} of track {track_id}")
