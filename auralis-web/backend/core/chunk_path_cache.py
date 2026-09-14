#!/usr/bin/env python3

"""
Chunk Path Resolution + Cache Lookup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Resolves a chunk's on-disk WAV path and checks the in-memory / on-disk cache
tiers for it. Extracted from ``ChunkedAudioProcessor`` (#4245): the
``_get_chunk_path`` / ``_get_wav_chunk_path`` / ``_lookup_cached_chunk``
trio, plus the cache-key-then-store pattern duplicated at each of
``process_chunk`` / ``process_all_chunks_async`` / ``get_wav_chunk_path``'s
cache-write sites.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.chunk_cache_manager import ChunkCacheManager
from core.encoding.atomic_io import is_wav_complete
from core.targets_hash import NO_TARGETS

logger = logging.getLogger("core.chunked_processor")


class ChunkPathCache:
    """Resolves chunk paths and checks/records cache hits for one cache identity.

    Owns no state beyond the identity tuple (track_id, file_signature, preset,
    intensity, targets_hash) and references to the collaborators that do the
    real work (``wav_encoder`` for path generation, ``cache_manager`` for the
    in-memory tier). The on-disk tier is checked directly here via
    ``Path.exists()`` + ``is_wav_complete()``.

    ``targets_hash`` (#4666) is part of the identity because mastering targets
    change the DSP branch that produced the bytes on disk. It is fixed at
    construction, so ``ChunkedAudioProcessor.__init__`` must load the track's
    targets BEFORE building this collaborator.
    """

    def __init__(
        self,
        track_id: int,
        file_signature: str,
        preset: str | None,
        intensity: float,
        wav_encoder: Any,
        cache_manager: ChunkCacheManager,
        targets_hash: str = NO_TARGETS,
    ) -> None:
        self.track_id = track_id
        self.file_signature = file_signature
        self.preset = preset
        self.intensity = intensity
        self.targets_hash = targets_hash
        self._wav_encoder = wav_encoder
        self._cache_manager = cache_manager

    def get_chunk_path(self, chunk_index: int) -> Path:
        """Get the on-disk WAV path for a chunk (independent of cache state)."""
        path = self._wav_encoder.get_chunk_path(
            track_id=self.track_id,
            file_signature=self.file_signature,
            preset=self.preset,
            intensity=self.intensity,
            chunk_index=chunk_index,
            targets_hash=self.targets_hash,
        )
        return Path(path)

    def cache_key(self, chunk_index: int) -> str:
        """The collapsed cache key shared by the in-memory and on-disk tiers.

        A single key (rather than separate WAV/in-memory keys) means a hit
        recorded by any caller is visible to every other caller (#4792).
        """
        return ChunkCacheManager.get_chunk_cache_key(
            self.track_id,
            self.file_signature,
            self.preset,
            self.intensity,
            chunk_index,
            self.targets_hash,
        )

    def lookup_cached(self, chunk_index: int) -> Path | None:
        """Check the in-memory cache, then the on-disk WAV cache, for chunk_index.

        A disk hit is recorded into the in-memory cache before returning, so
        the next lookup for this chunk takes the fast in-memory path.

        Returns the cached Path, or None on a genuine miss (must be processed).
        """
        cache_key = self.cache_key(chunk_index)
        cached_path: Path | None = self._cache_manager.get_cached_chunk_path(cache_key)
        if cached_path is not None:
            return cached_path

        wav_chunk_path = self.get_chunk_path(chunk_index)
        # A bare exists() check would serve a WAV truncated by an interrupted
        # write forever, since the cache key is stable across restarts (#4576).
        if wav_chunk_path.exists():
            if is_wav_complete(wav_chunk_path):
                self._cache_manager.cache_chunk_path(cache_key, wav_chunk_path)
                return wav_chunk_path
            logger.warning(
                f"Discarding truncated WAV chunk {chunk_index} at "
                f"{wav_chunk_path.name}; regenerating"
            )
        return None

    def store(self, chunk_index: int, path: Path) -> None:
        """Record ``path`` as the cached chunk for ``chunk_index``."""
        self._cache_manager.cache_chunk_path(self.cache_key(chunk_index), path)
