"""
Streamlined Cache Worker for Auralis Beta.9
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Simple background worker that builds two-tier caches:
- Priority 1: Next chunk (Tier 1) - critical for smooth playback
- Priority 2: Full track cache (Tier 2) - enables instant seeking
- Priority 3: Previous track - enables instant back button

Replaces complex multi-tier worker (373 lines) with simple predictive logic (~150 lines).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Optional
from pathlib import Path

from cache import streamlined_cache_manager, CHUNK_DURATION

logger = logging.getLogger(__name__)


class StreamlinedCacheWorker:
    """
    Simple background worker for building two-tier caches.

    Strategy:
    1. Always buffer next chunk (both original + processed)
    2. Build full track cache in background
    3. Keep previous track cached for instant back button
    """

    def __init__(self, cache_manager, library_manager):
        """
        Initialize streamlined cache worker.

        Args:
            cache_manager: StreamlinedCacheManager instance
            library_manager: LibraryManager to get track information
        """
        self.cache_manager = cache_manager
        self.library_manager = library_manager
        self.running = False
        self._worker_task = None

        # Track what we're currently building
        self._building_track_id: Optional[int] = None
        self._building_chunk_idx: int = 0

    async def start(self):
        """Start the background worker."""
        if not self.running:
            self.running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("🚀 Streamlined cache worker started")

    async def stop(self):
        """Stop the background worker."""
        self.running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Streamlined cache worker stopped")

    async def _worker_loop(self):
        """
        Main worker loop - runs continuously.

        Checks every 1 second for needed chunks and processes them.
        """
        try:
            while self.running:
                await asyncio.sleep(1.0)  # Check every second

                try:
                    await self._process_priorities()
                except Exception as e:
                    logger.error(f"Error in cache worker loop: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Cache worker loop cancelled")
            raise

    async def _process_priorities(self):
        """
        Process caching priorities:
        1. Next chunk (Tier 1 - critical)
        2. Full track cache (Tier 2 - background)
        3. Previous track (Tier 2 - nice to have)
        """
        if not self.cache_manager.current_track_id:
            return  # No track playing

        track_id = self.cache_manager.current_track_id
        current_chunk = self.cache_manager._get_current_chunk(
            self.cache_manager.current_position
        )
        preset = self.cache_manager.current_preset
        intensity = self.cache_manager.intensity

        # Get track from library
        track = self.library_manager.tracks.get_by_id(track_id)
        if not track:
            logger.warning(f"Track {track_id} not found in library")
            return

        # Priority 1: Ensure next chunk is cached (Tier 1)
        next_chunk_idx = current_chunk + 1
        await self._ensure_tier1_chunk(track, track_id, next_chunk_idx, preset, intensity)

        # Priority 2: Build full track cache in background (Tier 2)
        if not self.cache_manager.is_track_fully_cached(track_id):
            await self._build_tier2_cache(track, track_id, current_chunk, preset, intensity)

    async def _ensure_tier1_chunk(
        self,
        track,
        track_id: int,
        chunk_idx: int,
        preset: str,
        intensity: float
    ):
        """
        Ensure a chunk is cached in Tier 1 (both original and processed).

        This method proactively loads chunks into Tier 1 cache to ensure instant
        playback continuity and fast preset switching.

        Args:
            track: Track object from library
            track_id: Track ID
            chunk_idx: Chunk index to cache
            preset: Current preset
            intensity: Processing intensity
        """
        # Collect chunk paths to warm Tier 1 after processing
        tier1_chunks_to_warm = []

        # Check if original chunk is cached
        original_path, tier = await self.cache_manager.get_chunk(
            track_id, chunk_idx, preset=None, intensity=intensity
        )

        if original_path is None:
            # Process original chunk
            original_path = await self._process_chunk(
                track, track_id, chunk_idx, preset=None, intensity=intensity, tier="tier1"
            )

        # Add to warming list if we have the path
        if original_path:
            from pathlib import Path
            tier1_chunks_to_warm.append((chunk_idx, Path(original_path), None))

        # Check if processed chunk is cached (only if auto-mastering enabled)
        if self.cache_manager.auto_mastering_enabled:
            processed_path, tier = await self.cache_manager.get_chunk(
                track_id, chunk_idx, preset=preset, intensity=intensity
            )

            if processed_path is None:
                # Process with current preset
                processed_path = await self._process_chunk(
                    track, track_id, chunk_idx, preset=preset, intensity=intensity, tier="tier1"
                )

            # Add to warming list if we have the path
            if processed_path:
                from pathlib import Path
                tier1_chunks_to_warm.append((chunk_idx, Path(processed_path), preset))

        # Immediately warm Tier 1 with these chunks
        if tier1_chunks_to_warm:
            await self.cache_manager.warm_tier1_immediately(
                track_id=track_id,
                chunk_paths=tier1_chunks_to_warm,
                intensity=intensity
            )

    async def _build_tier2_cache(
        self,
        track,
        track_id: int,
        current_chunk: int,
        preset: str,
        intensity: float
    ):
        """
        Build full track cache (Tier 2) in background.

        Strategy:
        - Process chunks sequentially from start to end
        - Skip chunks already in Tier 1 or Tier 2
        - Process one chunk per iteration (avoid blocking)

        Args:
            track: Track object from library
            track_id: Track ID
            current_chunk: Current playback position chunk
            preset: Current preset
            intensity: Processing intensity
        """
        # Get track cache status
        status = self.cache_manager.get_track_cache_status(track_id)
        if not status:
            return  # Track not initialized yet

        # Reset building state if track changed
        if self._building_track_id != track_id:
            self._building_track_id = track_id
            self._building_chunk_idx = 0
            logger.info(f"Building Tier 2 cache for track {track_id} ({status.total_chunks} chunks)")

        # Find next uncached chunk
        for chunk_idx in range(self._building_chunk_idx, status.total_chunks):
            # Check if original chunk is cached
            if chunk_idx not in status.cached_chunks_original:
                await self._process_chunk(
                    track, track_id, chunk_idx, preset=None, intensity=intensity, tier="tier2"
                )
                self._building_chunk_idx = chunk_idx + 1
                return  # Process one chunk per iteration

            # Check if processed chunk is cached (only if auto-mastering enabled)
            if self.cache_manager.auto_mastering_enabled:
                if chunk_idx not in status.cached_chunks_processed:
                    await self._process_chunk(
                        track, track_id, chunk_idx, preset=preset, intensity=intensity, tier="tier2"
                    )
                    self._building_chunk_idx = chunk_idx + 1
                    return  # Process one chunk per iteration

        # All chunks processed
        if not self.cache_manager.is_track_fully_cached(track_id):
            logger.info(f"Tier 2 cache complete for track {track_id}")

    async def _process_chunk(
        self,
        track,
        track_id: int,
        chunk_idx: int,
        preset: Optional[str],
        intensity: float,
        tier: str
    ) -> Optional[str]:
        """
        Process a single chunk and add to cache.

        Args:
            track: Track object from library
            track_id: Track ID
            chunk_idx: Chunk index
            preset: Processing preset (None for original)
            intensity: Processing intensity
            tier: Target tier ("tier1" or "tier2")

        Returns:
            Path to processed chunk file, or None if processing failed
        """
        try:
            preset_str = "original" if preset is None else preset
            logger.debug(f"[{tier}] Processing chunk {chunk_idx} ({preset_str})")

            # Check if file exists
            if not Path(track.filepath).exists():
                logger.error(f"File not found: {track.filepath}")
                return None

            # Import here to avoid circular dependency
            from chunked_processor import ChunkedAudioProcessor

            # Create processor
            processor = ChunkedAudioProcessor(
                track_id=track_id,
                filepath=track.filepath,
                preset=preset,  # None for original
                intensity=intensity
            )

            # Process chunk with timeout (using thread-safe async method)
            timeout_seconds = 20 if tier == "tier1" else 60  # Tier 1 is urgent

            try:
                chunk_path = await asyncio.wait_for(
                    processor.process_chunk_safe(chunk_idx),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"[{tier}] Timeout processing chunk {chunk_idx} "
                    f"(exceeded {timeout_seconds}s limit)"
                )
                return None
            except FileNotFoundError as e:
                logger.error(f"[{tier}] File not found: {e}")
                return None
            except PermissionError as e:
                logger.error(f"[{tier}] Permission denied: {e}")
                return None

            # Add to cache
            if chunk_path:
                success = await self.cache_manager.add_chunk(
                    track_id=track_id,
                    chunk_idx=chunk_idx,
                    chunk_path=Path(chunk_path),
                    preset=preset,
                    intensity=intensity,
                    tier=tier
                )

                if success:
                    logger.info(
                        f"✅ [{tier}] Cached chunk {chunk_idx} ({preset_str}) "
                        f"for track {track_id}"
                    )
                else:
                    logger.warning(f"[{tier}] Failed to cache chunk {chunk_idx}")

            # Small delay to avoid CPU saturation
            await asyncio.sleep(0.05)

            return chunk_path

        except Exception as e:
            logger.error(f"[{tier}] Failed to process chunk {chunk_idx}: {e}", exc_info=True)
            return None

    async def trigger_immediate_processing(
        self,
        track_id: int,
        chunk_idx: int,
        preset: Optional[str],
        intensity: float
    ) -> bool:
        """
        Trigger immediate processing of a specific chunk (for cache misses).

        Used when user seeks or switches tracks and chunk is not cached.

        Args:
            track_id: Track ID
            chunk_idx: Chunk index
            preset: Preset (None for original)
            intensity: Processing intensity

        Returns:
            True if processing succeeded
        """
        track = self.library_manager.tracks.get_by_id(track_id)
        if not track:
            return False

        try:
            preset_str = "original" if preset is None else preset
            logger.info(f"⚡ IMMEDIATE: Processing chunk {chunk_idx} ({preset_str})")

            await self._process_chunk(
                track, track_id, chunk_idx, preset, intensity, tier="tier1"
            )

            return True

        except Exception as e:
            logger.error(f"Immediate processing failed: {e}")
            return False


# Global instance (initialized in main.py)
streamlined_worker: Optional[StreamlinedCacheWorker] = None
