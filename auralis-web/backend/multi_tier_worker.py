"""
Multi-Tier Buffer Worker
~~~~~~~~~~~~~~~~~~~~~~~~~

Enhanced buffer worker that uses multi-tier caching with branch prediction.
Intelligently prioritizes L1 > L2 > L3 chunk processing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Optional, List, Tuple
from pathlib import Path

from multi_tier_buffer import MultiTierBufferManager, CHUNK_DURATION

logger = logging.getLogger(__name__)


class MultiTierBufferWorker:
    """
    Enhanced background worker for multi-tier buffer management.

    Processes chunks in priority order:
    1. L1 cache misses (highest priority - instant switching)
    2. L2 cache misses (medium priority - fast switching)
    3. L3 cache misses (low priority - long-term buffering)
    """

    def __init__(self, buffer_manager: MultiTierBufferManager, library_manager):
        """
        Initialize multi-tier buffer worker.

        Args:
            buffer_manager: MultiTierBufferManager instance
            library_manager: LibraryManager to get track information
        """
        self.buffer_manager = buffer_manager
        self.library_manager = library_manager
        self.running = False
        self._worker_task = None

        # Processing queue with priorities
        self._processing_queue: List[Tuple[int, int, str, int, float]] = []  # (priority, track_id, preset, chunk_idx, intensity)
        self._queue_lock = asyncio.Lock()

    async def start(self):
        """Start the background worker."""
        if not self.running:
            self.running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("🚀 Multi-tier buffer worker started")

    async def stop(self):
        """Stop the background worker."""
        self.running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Multi-tier buffer worker stopped")

    async def _worker_loop(self):
        """
        Main worker loop - runs continuously.

        Checks every 1 second for needed chunks and processes them by priority.
        """
        try:
            while self.running:
                await asyncio.sleep(1.0)  # Check every second

                try:
                    await self._process_needed_chunks()
                except Exception as e:
                    logger.error(f"Error in multi-tier worker loop: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Multi-tier buffer worker loop cancelled")
            raise

    async def _process_needed_chunks(self):
        """
        Identify and process chunks that need buffering.

        Strategy:
        1. Check what's needed for L1 (current + next chunk, top presets)
        2. Check what's needed for L2 (branch scenarios)
        3. Check what's needed for L3 (long-term current preset)
        4. Process in priority order: L1 > L2 > L3
        """
        if not self.buffer_manager.current_track_id:
            return  # No track playing

        track_id = self.buffer_manager.current_track_id
        current_chunk = self.buffer_manager._get_current_chunk(
            self.buffer_manager.current_position
        )
        preset = self.buffer_manager.current_preset
        intensity = self.buffer_manager.intensity

        # Get track from library
        track = self.library_manager.tracks.get_by_id(track_id)
        if not track:
            logger.warning(f"Track {track_id} not found in library")
            return

        # Collect needed chunks for each tier
        l1_needed = await self._get_l1_needed_chunks(track_id, current_chunk, preset, intensity)
        l2_needed = await self._get_l2_needed_chunks(track_id, current_chunk, preset, intensity)
        l3_needed = await self._get_l3_needed_chunks(track_id, current_chunk, preset, intensity)

        # Process by priority
        for priority, preset_name, chunk_idx in l1_needed:
            await self._process_chunk(track, track_id, preset_name, chunk_idx, intensity, priority="L1")

        for priority, preset_name, chunk_idx in l2_needed:
            await self._process_chunk(track, track_id, preset_name, chunk_idx, intensity, priority="L2")

        # L3 is lower priority - only process if we have spare capacity
        if not l1_needed and not l2_needed:
            for priority, preset_name, chunk_idx in l3_needed[:2]:  # Limit L3 to 2 chunks per cycle
                await self._process_chunk(track, track_id, preset_name, chunk_idx, intensity, priority="L3")

    async def _get_l1_needed_chunks(
        self,
        track_id: int,
        current_chunk: int,
        preset: str,
        intensity: float
    ) -> List[Tuple[int, str, int]]:
        """
        Get chunks needed for L1 cache.

        Returns:
            List of (priority, preset, chunk_idx) tuples
        """
        needed = []

        # Always include current preset
        top_presets = [preset]

        # Add predicted presets
        predicted = self.buffer_manager.branch_predictor.predict_next_presets(preset, top_n=2)
        for pred_preset, prob in predicted:
            if prob > 0.15:  # Only high-confidence predictions
                top_presets.append(pred_preset)

        # Limit to top 3
        top_presets = top_presets[:3]

        # Check current and next chunk for these presets
        for chunk_offset in [0, 1]:
            chunk_idx = current_chunk + chunk_offset
            for cache_preset in top_presets:
                is_cached, _ = await self.buffer_manager.is_chunk_cached(
                    track_id, cache_preset, chunk_idx, intensity
                )

                if not is_cached:
                    # Priority: 0 = highest (current chunk, current preset)
                    priority = chunk_offset + (0 if cache_preset == preset else 1)
                    needed.append((priority, cache_preset, chunk_idx))

        return sorted(needed)  # Sort by priority

    async def _get_l2_needed_chunks(
        self,
        track_id: int,
        current_chunk: int,
        preset: str,
        intensity: float
    ) -> List[Tuple[int, str, int]]:
        """
        Get chunks needed for L2 cache (branch scenarios).

        Returns:
            List of (priority, preset, chunk_idx) tuples
        """
        needed = []

        # Get branch scenarios
        branches = self.buffer_manager.branch_predictor.predict_branches(
            preset, current_chunk, self.buffer_manager.current_position
        )

        for branch in branches:
            for chunk_idx in list(branch.chunk_range)[:3]:  # Limit to first 3 chunks per branch
                is_cached, _ = await self.buffer_manager.is_chunk_cached(
                    track_id, branch.preset, chunk_idx, intensity
                )

                if not is_cached:
                    # Priority based on branch probability (higher prob = lower priority number)
                    priority = 10 + int((1.0 - branch.probability) * 10)
                    needed.append((priority, branch.preset, chunk_idx))

        return sorted(needed)[:5]  # Limit to top 5 L2 chunks

    async def _get_l3_needed_chunks(
        self,
        track_id: int,
        current_chunk: int,
        preset: str,
        intensity: float
    ) -> List[Tuple[int, str, int]]:
        """
        Get chunks needed for L3 cache (long-term current preset).

        Returns:
            List of (priority, preset, chunk_idx) tuples
        """
        needed = []

        # Buffer 5-10 chunks ahead for current preset only
        for offset in range(2, 10):
            chunk_idx = current_chunk + offset
            is_cached, _ = await self.buffer_manager.is_chunk_cached(
                track_id, preset, chunk_idx, intensity
            )

            if not is_cached:
                # Priority: lower number = higher priority
                priority = 20 + offset
                needed.append((priority, preset, chunk_idx))

        return sorted(needed)

    async def _process_chunk(
        self,
        track,
        track_id: int,
        preset: str,
        chunk_idx: int,
        intensity: float,
        priority: str = "L1"
    ):
        """
        Process a single chunk and add to appropriate cache tier.

        Args:
            track: Track object from library
            track_id: Track ID
            preset: Processing preset
            chunk_idx: Chunk index
            intensity: Processing intensity
            priority: Cache tier priority ("IMMEDIATE", "L1", "L2", or "L3")
        """
        try:
            logger.debug(f"[{priority}] Processing: track={track_id}, preset={preset}, chunk={chunk_idx}")

            # Check if file exists before processing
            if not Path(track.filepath).exists():
                logger.error(f"[{priority}] File not found: {track.filepath}")
                return

            # Import here to avoid circular dependency
            from chunked_processor import ChunkedAudioProcessor

            # Create processor for this preset
            processor = ChunkedAudioProcessor(
                track_id=track_id,
                filepath=track.filepath,
                preset=preset,
                intensity=intensity
            )

            # Process the chunk with timeout
            # IMMEDIATE: 20s timeout (critical - user is waiting)
            # L1: 30s timeout (needs to be fast)
            # L2: 60s timeout (medium priority)
            # L3: 90s timeout (low priority, can take longer)
            if priority == "IMMEDIATE":
                timeout_seconds = 20
            elif priority == "L1":
                timeout_seconds = 30
            elif priority == "L2":
                timeout_seconds = 60
            else:  # L3
                timeout_seconds = 90

            try:
                chunk_path = await asyncio.wait_for(
                    asyncio.to_thread(processor.process_chunk, chunk_idx),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"[{priority}] Timeout processing chunk {chunk_idx} for track {track_id} "
                    f"(exceeded {timeout_seconds}s limit)"
                )
                return
            except FileNotFoundError as e:
                logger.error(f"[{priority}] File not found during processing: {e}")
                return
            except PermissionError as e:
                logger.error(f"[{priority}] Permission denied accessing file: {e}")
                return

            if chunk_path:
                # Add to appropriate cache tier based on priority
                from multi_tier_buffer import CacheEntry
                import time

                entry = CacheEntry(
                    track_id=track_id,
                    preset=preset,
                    chunk_idx=chunk_idx,
                    intensity=intensity,
                    timestamp=time.time(),
                    probability=1.0 if priority in ("IMMEDIATE", "L1") else (0.8 if priority == "L2" else 0.6)
                )

                # Add to appropriate tier
                if priority in ("IMMEDIATE", "L1"):
                    await self.buffer_manager.l1_cache.add_entry(entry)
                elif priority == "L2":
                    await self.buffer_manager.l2_cache.add_entry(entry)
                else:  # L3
                    await self.buffer_manager.l3_cache.add_entry(entry)

                logger.info(f"✅ [{priority}] Buffered: track={track_id}, preset={preset}, chunk={chunk_idx}")

            # Small delay to avoid CPU saturation
            await asyncio.sleep(0.05)

        except Exception as e:
            logger.error(f"[{priority}] Failed to buffer chunk {chunk_idx} for {preset}: {e}")

    async def trigger_immediate_processing(
        self,
        track_id: int,
        preset: str,
        chunk_idx: int,
        intensity: float
    ) -> bool:
        """
        Trigger immediate processing of a specific chunk (for cache misses during playback).

        This is called when user switches to a preset that's not cached.

        Args:
            track_id: Track ID
            preset: Preset to process
            chunk_idx: Chunk index
            intensity: Processing intensity

        Returns:
            True if processing succeeded, False otherwise
        """
        track = self.library_manager.tracks.get_by_id(track_id)
        if not track:
            return False

        try:
            logger.info(f"⚡ IMMEDIATE: Processing track={track_id}, preset={preset}, chunk={chunk_idx}")

            await self._process_chunk(track, track_id, preset, chunk_idx, intensity, priority="IMMEDIATE")

            return True

        except Exception as e:
            logger.error(f"Immediate processing failed: {e}")
            return False


# Global instance (will be initialized in main.py)
multi_tier_worker: Optional[MultiTierBufferWorker] = None
