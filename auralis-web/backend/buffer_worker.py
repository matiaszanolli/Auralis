"""
Buffer Worker for Predictive Chunk Processing

Background worker that processes chunks based on buffer manager's needs.
Runs continuously and processes chunks for all presets to enable instant switching.
"""

import asyncio
import logging
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class BufferWorker:
    """
    Background worker for processing chunks based on buffer manager needs.

    Continuously monitors what chunks need buffering and processes them in background.
    """

    def __init__(self, buffer_manager, library_manager):
        """
        Initialize buffer worker.

        Args:
            buffer_manager: BufferManager instance to get processing needs
            library_manager: LibraryManager to get track information
        """
        self.buffer_manager = buffer_manager
        self.library_manager = library_manager
        self.running = False
        self._worker_task = None

    async def start(self):
        """Start the background worker."""
        if not self.running:
            self.running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("🚀 Buffer worker started")

    async def stop(self):
        """Stop the background worker."""
        self.running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Buffer worker stopped")

    async def _worker_loop(self):
        """
        Main worker loop - runs continuously.

        Checks every 2 seconds what chunks need buffering and processes them.
        """
        try:
            while self.running:
                await asyncio.sleep(2.0)  # Check every 2 seconds

                try:
                    await self._process_needed_chunks()
                except Exception as e:
                    logger.error(f"Error in buffer worker loop: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Buffer worker loop cancelled")
            raise

    async def _process_needed_chunks(self):
        """
        Check what chunks need buffering and process them.
        """
        if not self.buffer_manager.current_track_id:
            return  # No track playing, nothing to buffer

        track_id = self.buffer_manager.current_track_id
        intensity = self.buffer_manager.intensity

        # Get what chunks need processing for all presets
        needed = self.buffer_manager.get_needed_chunks(track_id, intensity)

        if not needed:
            return  # Everything buffered, nothing to do

        # Get track from library
        track = self.library_manager.tracks.get_by_id(track_id)
        if not track:
            logger.warning(f"Track {track_id} not found in library")
            return

        # Import here to avoid circular dependency
        from chunked_processor import ChunkedAudioProcessor

        # Process needed chunks for each preset
        for preset, chunk_indices in needed.items():
            for chunk_idx in chunk_indices:
                # Check if already buffered (avoid race conditions)
                if self.buffer_manager.is_chunk_buffered(track_id, preset, chunk_idx):
                    continue

                try:
                    logger.info(f"🔄 Processing: track={track_id}, preset={preset}, chunk={chunk_idx}")

                    # Create processor for this preset
                    processor = ChunkedAudioProcessor(
                        track_id=track_id,
                        filepath=track.filepath,
                        preset=preset,
                        intensity=intensity
                    )

                    # Process the chunk
                    chunk_path = processor.process_chunk(chunk_idx)

                    # Mark as ready in buffer manager
                    self.buffer_manager.mark_chunk_ready(track_id, preset, chunk_idx, intensity)

                    logger.info(f"✅ Buffered: track={track_id}, preset={preset}, chunk={chunk_idx}")

                    # Small delay to avoid CPU saturation
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Failed to buffer chunk {chunk_idx} for {preset}: {e}")


# Global buffer worker instance (will be initialized in main.py)
buffer_worker: Optional[BufferWorker] = None
