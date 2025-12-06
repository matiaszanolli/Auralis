"""
Cache Adapter

Provides compatibility layer between SimpleChunkCache interface and StreamlinedCacheManager.
Allows code expecting SimpleChunkCache to work transparently with StreamlinedCacheManager.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
import numpy as np
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Any, Dict, Protocol

from auralis.io.unified_loader import load_audio
from auralis.io.saver import save as save_audio

logger = logging.getLogger(__name__)


class CacheManager(Protocol):
    """Protocol for cache manager interface."""

    async def get_chunk(
        self,
        track_id: int,
        chunk_idx: int,
        preset: Optional[str] = None,
        intensity: float = 1.0,
    ) -> Tuple[Optional[Path], str]:
        """Get chunk from cache."""
        ...

    async def add_chunk(
        self,
        track_id: int,
        chunk_idx: int,
        chunk_path: Path,
        preset: Optional[str] = None,
        intensity: float = 1.0,
        tier: str = "auto",
    ) -> bool:
        """Add chunk to cache."""
        ...


class StreamlinedCacheAdapter:
    """
    Adapter that makes StreamlinedCacheManager compatible with SimpleChunkCache interface.

    Bridges the gap between two cache implementations:
    - SimpleChunkCache: Stores (audio_array, sample_rate) tuples in memory
    - StreamlinedCacheManager: Stores chunk file paths on disk

    This adapter presents the SimpleChunkCache interface while delegating to StreamlinedCacheManager.
    """

    def __init__(self, manager: CacheManager) -> None:
        """
        Initialize adapter with a StreamlinedCacheManager instance.

        Args:
            manager: StreamlinedCacheManager instance to wrap

        Raises:
            ValueError: If manager is not a valid CacheManager
        """
        self.manager: CacheManager = manager
        self._temp_chunk_cache: Dict[str, Tuple[np.ndarray, int]] = {}  # Temporary in-memory cache for current session

    async def get(
        self,
        track_id: int,
        chunk_idx: int,
        preset: str,
        intensity: float
    ) -> Optional[Tuple[np.ndarray, int]]:
        """
        Get chunk from cache (SimpleChunkCache interface).

        Tries StreamlinedCacheManager first, falls back to temp cache.

        Args:
            track_id: Track ID
            chunk_idx: Chunk index
            preset: Processing preset
            intensity: Processing intensity

        Returns:
            (audio_array, sample_rate) tuple or None if not cached
        """
        try:
            # Try to get from StreamlinedCacheManager
            chunk_path, tier = await self.manager.get_chunk(
                track_id=track_id,
                chunk_idx=chunk_idx,
                preset=preset,
                intensity=intensity
            )

            if chunk_path:
                try:
                    # Load audio from cached chunk file
                    audio, sr = load_audio(str(chunk_path))
                    logger.debug(f"✅ Cache HIT ({tier}): track {track_id}, chunk {chunk_idx}, preset {preset}")
                    return (audio, sr)
                except Exception as e:
                    logger.warning(f"Failed to load cached chunk from {chunk_path}: {e}")
                    return None
        except Exception as e:
            logger.debug(f"StreamlinedCacheManager.get_chunk failed: {e}")

        # Try temp in-memory cache as fallback
        cache_key = f"{track_id}_{chunk_idx}_{preset}_{intensity:.2f}"
        if cache_key in self._temp_chunk_cache:
            logger.debug(f"✅ Temp cache HIT: track {track_id}, chunk {chunk_idx}")
            return self._temp_chunk_cache[cache_key]

        return None

    async def put(
        self,
        track_id: int,
        chunk_idx: int,
        preset: str,
        intensity: float,
        audio: np.ndarray,
        sample_rate: int
    ) -> None:
        """
        Store chunk in cache (SimpleChunkCache interface).

        Saves to temporary file and adds to StreamlinedCacheManager.
        Also keeps in temporary in-memory cache for quick access.

        Args:
            track_id: Track ID
            chunk_idx: Chunk index
            preset: Processing preset
            intensity: Processing intensity
            audio: Audio samples (numpy array)
            sample_rate: Sample rate in Hz
        """
        try:
            # Save to temporary file
            temp_dir = Path(tempfile.gettempdir()) / "auralis_cache_adapter"
            temp_dir.mkdir(parents=True, exist_ok=True)

            chunk_path = temp_dir / f"chunk_{track_id}_{chunk_idx}_{preset}_{intensity:.2f}.wav"

            # Save audio to temporary file
            save_audio(str(chunk_path), audio, sample_rate)

            # Add to StreamlinedCacheManager
            try:
                success = await self.manager.add_chunk(
                    track_id=track_id,
                    chunk_idx=chunk_idx,
                    chunk_path=chunk_path,
                    preset=preset,
                    intensity=intensity,
                    tier="auto"
                )
                if success:
                    logger.debug(f"✅ Cached chunk {chunk_idx} for track {track_id} (preset: {preset})")
            except Exception as e:
                logger.warning(f"Failed to add chunk to StreamlinedCacheManager: {e}")
        except Exception as e:
            logger.warning(f"Failed to save chunk to cache: {e}")

        # Also store in temporary in-memory cache for fast access
        cache_key = f"{track_id}_{chunk_idx}_{preset}_{intensity:.2f}"
        self._temp_chunk_cache[cache_key] = (audio, sample_rate)

    def clear(self) -> None:
        """Clear temporary in-memory cache."""
        self._temp_chunk_cache.clear()
        logger.debug("Temp chunk cache cleared")
