#!/usr/bin/env python3

"""
Chunk Cache Manager
~~~~~~~~~~~~~~~~~~~

Unified cache key generation and lookup for audio chunks.

Provides a centralized service for:
- Generating consistent cache keys for chunks, fingerprints, and WAV files
- Looking up cached paths with existence validation
- Storing cache entries

This eliminates duplicate cache key patterns and centralizes caching logic.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# On-disk chunk cache (/tmp/auralis_chunks) bound (#3834). Mirrors the 512 MB
# in-memory cap of SimpleChunkCache. All ChunkedAudioProcessor instances share
# the same directory, so the reaper is global and runs on a throttle.
MAX_CHUNK_DISK_BYTES = 512 * 1024 * 1024  # 512 MB
PRUNE_EVERY_N_WRITES = 32  # amortise the directory scan across writes


class ChunkCacheManager:
    """
    Unified cache key generation and lookup for audio chunks.

    This service consolidates all cache-related operations for chunked audio
    processing, ensuring consistent cache key patterns and reducing duplication.

    Cache keys are structured as:
    - Chunk: {track_id}_{file_sig}_{preset}_{intensity}_chunk_{chunk_index}
    - WAV: {track_id}_{file_sig}_{preset}_{intensity}_wav_{chunk_index}
    - Fingerprint: fingerprint_{track_id}_{file_sig}

    The cache dictionary is shared across instances and typically lives in
    ChunkedAudioProcessor or a global cache service.
    """

    @staticmethod
    def get_chunk_cache_key(
        track_id: int,
        file_signature: str,
        preset: str | None,
        intensity: float,
        chunk_index: int
    ) -> str:
        """
        Generate cache key for a processed audio chunk.

        Format: {track_id}_{file_sig}_{preset}_{intensity}_chunk_{chunk_index}

        Args:
            track_id: Database track ID
            file_signature: 8-char file signature (from FileSignatureService)
            preset: Processing preset (adaptive, gentle, warm, etc.) or None
            intensity: Processing intensity (0.0 - 1.0)
            chunk_index: Chunk index (0-based)

        Returns:
            Cache key string

        Examples:
            >>> ChunkCacheManager.get_chunk_cache_key(123, "a3b4c5d6", "adaptive", 0.8, 0)
            '123_a3b4c5d6_adaptive_0.8_chunk_0'
        """
        return f"{track_id}_{file_signature}_{preset}_{intensity}_chunk_{chunk_index}"

    @staticmethod
    def get_wav_cache_key(
        track_id: int,
        file_signature: str,
        preset: str | None,
        intensity: float,
        chunk_index: int
    ) -> str:
        """
        Generate cache key for a WAV-encoded audio chunk.

        Format: {track_id}_{file_sig}_{preset}_{intensity}_wav_{chunk_index}

        This is separate from the standard chunk key to allow independent
        caching of different output formats.

        Args:
            track_id: Database track ID
            file_signature: 8-char file signature
            preset: Processing preset or None
            intensity: Processing intensity (0.0 - 1.0)
            chunk_index: Chunk index (0-based)

        Returns:
            Cache key string

        Examples:
            >>> ChunkCacheManager.get_wav_cache_key(123, "a3b4c5d6", "adaptive", 0.8, 0)
            '123_a3b4c5d6_adaptive_0.8_wav_0'
        """
        return f"{track_id}_{file_signature}_{preset}_{intensity}_wav_{chunk_index}"

    @staticmethod
    def get_fingerprint_cache_key(track_id: int, file_signature: str) -> str:
        """
        Generate cache key for track-level fingerprint.

        Format: fingerprint_{track_id}_{file_sig}

        Fingerprints are track-specific (not chunk-specific), so the cache key
        only includes track_id and file_signature.

        Args:
            track_id: Database track ID
            file_signature: 8-char file signature

        Returns:
            Cache key string

        Examples:
            >>> ChunkCacheManager.get_fingerprint_cache_key(123, "a3b4c5d6")
            'fingerprint_123_a3b4c5d6'
        """
        return f"fingerprint_{track_id}_{file_signature}"

    # Shared across all instances so the on-disk reaper throttle and the prune
    # itself are coordinated for the single /tmp/auralis_chunks directory (#3834).
    _prune_lock: "threading.Lock" = threading.Lock()
    _write_counter: int = 0

    def __init__(
        self,
        cache_dict: dict[str, Any],
        max_disk_bytes: int = MAX_CHUNK_DISK_BYTES,
        prune_every: int = PRUNE_EVERY_N_WRITES,
    ) -> None:
        """
        Initialize cache manager with shared cache dictionary.

        Args:
            cache_dict: Shared cache dictionary (typically from ChunkedAudioProcessor)
                       Maps cache keys to paths (str) or fingerprints (dict)
            max_disk_bytes: Cap on the on-disk chunk directory; the oldest WAVs
                are pruned past this (#3834). Default 512 MB.
            prune_every: Run the on-disk prune once every this many cached paths,
                amortising the directory scan.
        """
        self._cache = cache_dict
        self._max_disk_bytes = max_disk_bytes
        self._prune_every = max(1, prune_every)

    def get_cached_chunk_path(self, cache_key: str) -> Path | None:
        """
        Lookup chunk path in cache and verify it exists on disk.

        Args:
            cache_key: Cache key (from get_chunk_cache_key or get_wav_cache_key)

        Returns:
            Path to cached chunk file if it exists, None otherwise

        Examples:
            >>> manager = ChunkCacheManager({})
            >>> manager.cache_chunk_path("key", Path("/tmp/chunk.wav"))
            >>> manager.get_cached_chunk_path("key")
            PosixPath('/tmp/chunk.wav')
        """
        cached_value = self._cache.get(cache_key)

        # Cache value should be a string path
        if cached_value is None:
            return None

        if not isinstance(cached_value, str):
            logger.warning(
                f"Cache key '{cache_key}' has non-string value (type={type(cached_value).__name__}). "
                f"Expected path string. Ignoring."
            )
            return None

        # Convert to Path and verify existence
        path = Path(cached_value)
        if not path.exists():
            logger.debug(f"Cached path {path} no longer exists. Cache miss.")
            return None

        logger.debug(f"Cache hit: {cache_key} → {path}")
        return path

    def cache_chunk_path(self, cache_key: str, path: Path) -> None:
        """
        Store chunk path in cache.

        Args:
            cache_key: Cache key
            path: Path to chunk file (must exist on disk)

        Examples:
            >>> manager = ChunkCacheManager({})
            >>> manager.cache_chunk_path("key", Path("/tmp/chunk.wav"))
        """
        if not path.exists():
            logger.warning(
                f"Attempted to cache non-existent path: {path}. "
                f"This may indicate a processing error."
            )

        self._cache[cache_key] = str(path)
        logger.debug(f"Cached: {cache_key} → {path}")

        # Bound the on-disk chunk directory (#3834). The dict is per-instance and
        # small, but every processor writes WAVs to the same dir, which would
        # otherwise grow unbounded over a long session.
        self._maybe_prune(path.parent)

    def _maybe_prune(self, chunk_dir: Path) -> None:
        """Run the on-disk reaper once every `prune_every` cached paths.

        A class-level counter + lock coordinates the throttle across every
        ChunkCacheManager instance, since they all share one chunk directory.
        """
        cls = type(self)
        with cls._prune_lock:
            cls._write_counter += 1
            if cls._write_counter < self._prune_every:
                return
            cls._write_counter = 0
            # Prune under the lock so concurrent writers don't launch overlapping
            # reapers; a scan of a few hundred files is sub-millisecond-to-ms.
            self.prune_chunk_directory(chunk_dir, self._max_disk_bytes)

    @staticmethod
    def prune_chunk_directory(chunk_dir: Path, max_bytes: int) -> tuple[int, int]:
        """Delete the oldest files in *chunk_dir* (by mtime) until the directory's
        total size is within *max_bytes* (#3834).

        mtime-ordering means just-written chunks survive and the coldest tracks'
        WAVs are reclaimed first. Deleting a file another stream still references
        is safe: that stream's get_cached_chunk_path re-checks existence and
        treats a missing file as a cache miss (reprocess). Best-effort — per-file
        errors are logged, never raised.

        Returns (files_deleted, bytes_reclaimed).
        """
        try:
            entries: list[tuple[float, int, Path]] = []
            total = 0
            for p in chunk_dir.iterdir():
                if not p.is_file():
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                entries.append((st.st_mtime, st.st_size, p))
                total += st.st_size
        except OSError as e:
            logger.debug(f"Chunk-dir prune skipped ({chunk_dir}): {e}")
            return (0, 0)

        if total <= max_bytes:
            return (0, 0)

        entries.sort(key=lambda e: e[0])  # oldest mtime first
        deleted = 0
        reclaimed = 0
        for _mtime, size, p in entries:
            if total <= max_bytes:
                break
            try:
                p.unlink()
                deleted += 1
                reclaimed += size
                total -= size
            except OSError as e:
                logger.warning(f"Could not prune cached chunk {p}: {e}")

        if deleted:
            logger.info(
                f"Pruned {deleted} cached chunk file(s) from {chunk_dir}, "
                f"reclaimed {reclaimed / 1024 / 1024:.1f} MB (cap {max_bytes / 1024 / 1024:.0f} MB)"
            )
        return (deleted, reclaimed)

    def get_cached_fingerprint(self, cache_key: str) -> dict[str, Any] | None:
        """
        Lookup track-level fingerprint in cache.

        Args:
            cache_key: Fingerprint cache key (from get_fingerprint_cache_key)

        Returns:
            Cached fingerprint dict or None if not cached

        Examples:
            >>> manager = ChunkCacheManager({})
            >>> manager.cache_fingerprint("key", {"tempo": 120, "loudness": -14})
            >>> manager.get_cached_fingerprint("key")
            {'tempo': 120, 'loudness': -14}
        """
        cached_value = self._cache.get(cache_key)

        # Fingerprints are stored as dicts
        if cached_value is None:
            return None

        if not isinstance(cached_value, dict):
            logger.warning(
                f"Fingerprint cache key '{cache_key}' has non-dict value "
                f"(type={type(cached_value).__name__}). Expected fingerprint dict. Ignoring."
            )
            return None

        logger.debug(f"Fingerprint cache hit: {cache_key}")
        return cached_value

    def cache_fingerprint(self, cache_key: str, fingerprint: dict[str, Any]) -> None:
        """
        Store track-level fingerprint in cache.

        This avoids expensive fingerprint analysis (especially librosa tempo
        detection) for every chunk, reducing processing time by ~0.5-1s per chunk.

        Args:
            cache_key: Fingerprint cache key
            fingerprint: Complete 25D fingerprint dictionary

        Examples:
            >>> manager = ChunkCacheManager({})
            >>> fp = {"tempo": 120, "loudness": -14, "spectral_centroid": 2500}
            >>> manager.cache_fingerprint("key", fp)
        """
        self._cache[cache_key] = fingerprint
        logger.debug(f"Cached fingerprint: {cache_key} ({len(fingerprint)} metrics)")

    def clear_track_cache(
        self,
        track_id: int,
        file_signature: str,
        preset: str | None = None,
        intensity: float | None = None
    ) -> int:
        """
        Clear all cached entries for a specific track.

        Args:
            track_id: Database track ID
            file_signature: 8-char file signature
            preset: If provided, only clear chunks with this preset
            intensity: If provided, only clear chunks with this intensity

        Returns:
            Number of cache entries removed

        Examples:
            >>> manager = ChunkCacheManager({})
            >>> # Cache some chunks
            >>> # ...
            >>> removed = manager.clear_track_cache(123, "a3b4c5d6")
            >>> removed
            15
        """
        # Build prefix pattern for matching
        if preset is not None and intensity is not None:
            # Clear specific preset/intensity combination
            prefix = f"{track_id}_{file_signature}_{preset}_{intensity}_"
        else:
            # Clear all entries for this track
            prefix = f"{track_id}_{file_signature}_"

        # Also clear fingerprint
        fingerprint_key = self.get_fingerprint_cache_key(track_id, file_signature)

        # Find matching keys
        keys_to_remove = [
            key for key in self._cache.keys()
            if key.startswith(prefix) or key == fingerprint_key
        ]

        # Remove entries
        for key in keys_to_remove:
            del self._cache[key]

        if keys_to_remove:
            logger.info(
                f"Cleared {len(keys_to_remove)} cache entries for track {track_id} "
                f"(signature={file_signature}, preset={preset}, intensity={intensity})"
            )

        return len(keys_to_remove)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get cache statistics for monitoring and debugging.

        Returns:
            Dictionary with:
            - total_entries: Total number of cached items
            - chunk_entries: Number of processed chunk paths
            - wav_entries: Number of WAV chunk paths
            - fingerprint_entries: Number of cached fingerprints

        Examples:
            >>> manager = ChunkCacheManager({})
            >>> stats = manager.get_statistics()
            >>> stats
            {'total_entries': 0, 'chunk_entries': 0, 'wav_entries': 0, 'fingerprint_entries': 0}
        """
        total = len(self._cache)

        # Count entry types by key patterns
        chunk_count = sum(1 for key in self._cache if "_chunk_" in key)
        wav_count = sum(1 for key in self._cache if "_wav_" in key)
        fingerprint_count = sum(1 for key in self._cache if key.startswith("fingerprint_"))

        return {
            "total_entries": total,
            "chunk_entries": chunk_count,
            "wav_entries": wav_count,
            "fingerprint_entries": fingerprint_count
        }
