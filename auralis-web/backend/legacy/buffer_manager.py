"""
Smart Buffer Manager for Auralis

Maintains a 1-chunk-ahead buffer for all presets to enable instant preset switching.
Monitors playback position and pre-processes upcoming chunks in the background.
"""

import asyncio
import logging
from typing import Dict, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)

# Available presets for buffering
AVAILABLE_PRESETS = ["adaptive", "gentle", "warm", "bright", "punchy"]
CHUNK_DURATION = 30  # seconds


class BufferManager:
    """
    Manages pre-processing of audio chunks for instant preset switching.

    Strategy:
    - Track current playback position
    - Always keep 1 chunk ahead buffered for all presets + original
    - When position advances, buffer the next chunk for all presets
    - Enables zero-wait preset switching
    """

    def __init__(self):
        self.current_track_id: Optional[int] = None
        self.current_position: float = 0.0  # seconds
        self.intensity: float = 1.0

        # Track which chunks are buffered for each preset
        # Format: {track_id: {preset: {chunk_idx, chunk_idx+1}}}
        self.buffered_chunks: Dict[int, Dict[str, Set[int]]] = {}

        # Active processing tasks to avoid duplicate work
        self.processing_tasks: Set[str] = set()

        # Lock for thread safety
        self._lock = asyncio.Lock()

    def _get_current_chunk(self, position: float) -> int:
        """Calculate which chunk contains the given position."""
        return int(position // CHUNK_DURATION)

    def _get_task_key(self, track_id: int, preset: str, chunk_idx: int, intensity: float) -> str:
        """Generate unique key for a processing task."""
        return f"{track_id}_{preset}_{intensity}_{chunk_idx}"

    async def update_position(self, track_id: int, position: float, intensity: float = 1.0):
        """
        Update current playback position and trigger buffering if needed.

        Args:
            track_id: Current track ID
            position: Current position in seconds
            intensity: Processing intensity (0.0-1.0)
        """
        async with self._lock:
            # Check if track changed
            track_changed = track_id != self.current_track_id

            self.current_track_id = track_id
            self.current_position = position
            self.intensity = intensity

            current_chunk = self._get_current_chunk(position)
            next_chunk = current_chunk + 1

            # Initialize buffered chunks tracking for this track
            if track_id not in self.buffered_chunks:
                self.buffered_chunks[track_id] = {}

            # If track just changed, clear old track buffers to free memory
            if track_changed:
                old_tracks = [tid for tid in self.buffered_chunks.keys() if tid != track_id]
                for old_track in old_tracks:
                    del self.buffered_chunks[old_track]
                logger.info(f"Cleared buffers for old tracks: {old_tracks}")

            logger.debug(f"Position update: track={track_id}, pos={position:.1f}s, chunk={current_chunk}")

            # Check what needs buffering for instant preset switching
            await self._ensure_buffers(track_id, current_chunk, next_chunk, intensity)

    async def _ensure_buffers(self, track_id: int, current_chunk: int, next_chunk: int, intensity: float):
        """
        Ensure current and next chunks are buffered for all presets.

        For instant preset switching, we need:
        - Current chunk for all presets (in case user switches now)
        - Next chunk for all presets (in case user switches while playing)
        """
        # Track what needs to be buffered
        # Actual processing will be triggered by the caller

        for preset in AVAILABLE_PRESETS:
            if preset not in self.buffered_chunks[track_id]:
                self.buffered_chunks[track_id][preset] = set()

            buffered = self.buffered_chunks[track_id][preset]

            # Check which chunks need buffering
            chunks_to_buffer = []
            if current_chunk not in buffered:
                chunks_to_buffer.append(current_chunk)
            if next_chunk not in buffered:
                chunks_to_buffer.append(next_chunk)

            # Schedule buffering tasks
            for chunk_idx in chunks_to_buffer:
                task_key = self._get_task_key(track_id, preset, chunk_idx, intensity)

                if task_key not in self.processing_tasks:
                    self.processing_tasks.add(task_key)
                    logger.info(f"🔄 Buffering: track={track_id}, preset={preset}, chunk={chunk_idx}")
                    # Actual processing will be triggered by caller with processor instance
                    # This is just tracking

    def mark_chunk_ready(self, track_id: int, preset: str, chunk_idx: int, intensity: float):
        """
        Mark a chunk as buffered and ready.

        Args:
            track_id: Track ID
            preset: Processing preset
            chunk_idx: Chunk index
            intensity: Processing intensity
        """
        if track_id not in self.buffered_chunks:
            self.buffered_chunks[track_id] = {}
        if preset not in self.buffered_chunks[track_id]:
            self.buffered_chunks[track_id][preset] = set()

        self.buffered_chunks[track_id][preset].add(chunk_idx)

        # Remove from processing tasks
        task_key = self._get_task_key(track_id, preset, chunk_idx, intensity)
        self.processing_tasks.discard(task_key)

        logger.debug(f"✅ Chunk ready: track={track_id}, preset={preset}, chunk={chunk_idx}")

    def get_needed_chunks(self, track_id: int, intensity: float) -> Dict[str, Set[int]]:
        """
        Get chunks that need buffering for all presets.

        Returns:
            Dict mapping preset -> set of chunk indices that need processing
        """
        if not self.current_track_id or track_id != self.current_track_id:
            return {}

        current_chunk = self._get_current_chunk(self.current_position)
        next_chunk = current_chunk + 1

        needed = {}
        for preset in AVAILABLE_PRESETS:
            buffered = self.buffered_chunks.get(track_id, {}).get(preset, set())

            chunks_needed = set()
            if current_chunk not in buffered:
                chunks_needed.add(current_chunk)
            if next_chunk not in buffered:
                chunks_needed.add(next_chunk)

            if chunks_needed:
                needed[preset] = chunks_needed

        return needed

    def is_chunk_buffered(self, track_id: int, preset: str, chunk_idx: int) -> bool:
        """Check if a specific chunk is already buffered."""
        return chunk_idx in self.buffered_chunks.get(track_id, {}).get(preset, set())

    def clear_track_buffers(self, track_id: int):
        """Clear all buffers for a specific track."""
        if track_id in self.buffered_chunks:
            del self.buffered_chunks[track_id]
            logger.info(f"Cleared all buffers for track {track_id}")


# Global buffer manager instance
buffer_manager = BufferManager()
