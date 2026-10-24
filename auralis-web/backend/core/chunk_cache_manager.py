#!/usr/bin/env python3

"""
Chunk Cache Manager
~~~~~~~~~~~~~~~~~~~

Unified cache key generation and lookup for audio chunks.

Provides a centralized service for:
- Generating consistent cache keys for chunks and WAV files
- Looking up cached paths with existence validation
- Storing cache entries

This eliminates duplicate cache key patterns and centralizes caching logic.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from pathlib import Path
from typing import Any

from core.encoding.atomic_io import is_wav_complete
from core.targets_hash import NO_TARGETS

from .chunk_disk_prune import (  # noqa: F401
    MAX_CHUNK_DISK_BYTES,
    PRUNE_EVERY_N_WRITES,
    ChunkDiskPruneMixin,
)

logger = logging.getLogger(__name__)


# Canonical intensity precision for every chunk-cache key and on-disk filename
# (#5474). Each tier used to format intensity at its own precision — .1f in
# cache/models.py, the raw float in the on-disk key and WAV filename — so two
# requests in the same 0.1 bucket could be served audio rendered for a
# different off-grid intensity, and float noise (0.30000000000000004) minted
# its own unreachable disk entries. Quantise once here; every consumer imports
# this function rather than formatting intensity itself.
INTENSITY_KEY_DECIMALS = 1


def intensity_cache_key(intensity: float) -> float:
    """Bucket an intensity to the chunk cache's canonical 0.1 granularity."""
    return round(float(intensity), INTENSITY_KEY_DECIMALS)


class ChunkCacheManager(ChunkDiskPruneMixin):
    """
    Unified cache key generation and lookup for audio chunks.

    This service consolidates all cache-related operations for chunked audio
    processing, ensuring consistent cache key patterns and reducing duplication.

    Cache keys are structured as:
    - Chunk: {track_id}_{file_sig}_{preset}_{intensity}_{targets_hash}_chunk_{chunk_index}

    ``targets_hash`` (#4666) keeps the prefix-based clear_track_cache()
    patterns intact — it sits after intensity, so both the
    "{track}_{sig}_" and "{track}_{sig}_{preset}_{intensity}_" prefixes
    still match every chunk of a track.

    One key format, deliberately: both process_chunk() and
    get_wav_chunk_path() in ChunkedAudioProcessor resolve to the exact same
    on-disk file via WAVEncoder.get_chunk_path(), so a second WAV-specific
    key would make a hit recorded by one caller invisible to the other and
    leave the on-disk tier write-only from process_chunk()'s side (#4792).
    Do not split get_chunk_cache_key.

    The cache dictionary is shared across instances and typically lives in
    ChunkedAudioProcessor or a global cache service.
    """

    @staticmethod
    def get_chunk_cache_key(
        track_id: int,
        file_signature: str,
        preset: str | None,
        intensity: float,
        chunk_index: int,
        targets_hash: str = NO_TARGETS,
    ) -> str:
        """
        Generate cache key for a processed audio chunk.

        Format:
        {track_id}_{file_sig}_{preset}_{intensity}_{targets_hash}_chunk_{chunk_index}

        Args:
            track_id: Database track ID
            file_signature: 8-char file signature (from FileSignatureService)
            preset: Processing preset ('adaptive') or None
            intensity: Processing intensity (0.0 - 1.0)
            chunk_index: Chunk index (0-based)
            targets_hash: Content hash of the processor's mastering_targets
                (core/targets_hash.get_targets_hash), "none" when absent.
                #4666: targets change the DSP branch
                AudioProcessingPipeline.apply_enhancement takes, so chunks
                rendered with targets must not be served to a processor
                without them (or vice versa). A track's targets typically
                appear mid-session, once the background fingerprint queue
                fills in what __init__ deliberately did not extract
                (extract_if_missing=False) — without this component the
                pre-targets chunks stayed cached and were mixed with
                post-targets ones, producing an audible tonal/level shift
                mid-track.

        Returns:
            Cache key string

        Examples:
            >>> ChunkCacheManager.get_chunk_cache_key(123, "a3b4c5d6", "adaptive", 0.8, 0)
            '123_a3b4c5d6_adaptive_0.8_none_chunk_0'
        """
        return (
            f"{track_id}_{file_signature}_{preset}_{intensity_cache_key(intensity)}_"
            f"{targets_hash}_chunk_{chunk_index}"
        )

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
            cache_key: Cache key (from get_chunk_cache_key)

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

        # Convert to Path and verify the file is present AND complete.
        # #4576: an existence-only gate served a WAV truncated by an
        # interrupted write as a hit forever — cache keys embed CACHE_VERSION,
        # track id, file signature, preset and intensity, so the poisoned entry
        # survived restarts and only a manual cache clear recovered.
        path = Path(cached_value)
        if not path.exists():
            logger.debug(f"Cached path {path} no longer exists. Cache miss.")
            return None

        if not is_wav_complete(path):
            logger.warning(
                f"Cached WAV {path} is truncated — evicting and treating as a miss."
            )
            self._cache.pop(cache_key, None)
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
        # Both gates must agree on what counts as a valid entry (#4576),
        # otherwise a truncated file is refused on read but still recorded here.
        if not path.exists():
            logger.warning(
                f"Attempted to cache non-existent path: {path}. "
                f"This may indicate a processing error."
            )
        elif not is_wav_complete(path):
            logger.warning(
                f"Refusing to cache truncated WAV: {path}. "
                f"This may indicate an interrupted write."
            )
            # Still run the reaper: the on-disk cap (#3834) bounds the shared
            # chunk directory and must not become content-dependent — a run of
            # bad writes would otherwise let the directory grow unbounded.
            self._maybe_prune(path.parent)
            return

        self._cache[cache_key] = str(path)
        logger.debug(f"Cached: {cache_key} → {path}")

        # Bound the on-disk chunk directory (#3834). The dict is per-instance and
        # small, but every processor writes WAVs to the same dir, which would
        # otherwise grow unbounded over a long session.
        self._maybe_prune(path.parent)

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
        # Build prefix pattern for matching. The intensity component must be
        # formatted exactly as get_chunk_cache_key formats it (#5474), so the
        # prefix matches entries recorded under float-noise inputs too.
        if preset is not None and intensity is not None:
            # Clear specific preset/intensity combination
            prefix = f"{track_id}_{file_signature}_{preset}_{intensity_cache_key(intensity)}_"
        else:
            # Clear all entries for this track
            prefix = f"{track_id}_{file_signature}_"

        # Find matching keys
        keys_to_remove = [
            key for key in self._cache.keys()
            if key.startswith(prefix)
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
