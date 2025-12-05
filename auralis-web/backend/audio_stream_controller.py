#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Audio Stream Controller
~~~~~~~~~~~~~~~~~~~~~~~

Manages real-time audio streaming via WebSocket for enhanced audio playback.

Handles:
- Loading tracks and creating ChunkedProcessor instances
- Processing chunks on-demand with fast-start optimization
- Streaming PCM samples to connected WebSocket clients
- Managing crossfading at chunk boundaries
- Error handling and recovery

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import json
import numpy as np
import logging
from pathlib import Path
from typing import Optional, Callable
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class AudioStreamController:
    """
    Manages real-time audio streaming via WebSocket.

    Streams processed audio chunks as PCM samples to frontend for playback.
    Handles fast-start optimization (first chunk processed quickly),
    crossfading at boundaries, and error recovery.
    """

    def __init__(self, chunked_processor_class=None, library_manager=None):
        """
        Initialize AudioStreamController.

        Args:
            chunked_processor_class: ChunkedAudioProcessor class for processing
            library_manager: LibraryManager instance for track lookup
        """
        self.chunked_processor_class = chunked_processor_class
        self.library_manager = library_manager
        self.active_streams = {}  # track_id -> streaming task

    async def stream_enhanced_audio(
        self,
        track_id: int,
        preset: str,
        intensity: float,
        websocket: WebSocket,
        on_progress: Optional[Callable] = None
    ) -> None:
        """
        Stream enhanced audio chunks to client via WebSocket.

        Args:
            track_id: Track ID to process and stream
            preset: Processing preset (adaptive, gentle, warm, etc.)
            intensity: Processing intensity (0.0-1.0)
            websocket: WebSocket connection to client
            on_progress: Optional callback for progress updates

        Raises:
            ValueError: If track not found or processor unavailable
            Exception: If processing or streaming fails
        """
        if not self.chunked_processor_class:
            raise ValueError("ChunkedProcessor not available")

        if not self.library_manager:
            raise ValueError("LibraryManager not available")

        # Get track from library
        try:
            track = self.library_manager.tracks.get_by_id(track_id)
            if not track:
                await self._send_error(websocket, track_id, "Track not found")
                return

            if not Path(track.filepath).exists():
                await self._send_error(
                    websocket, track_id, f"Audio file not found: {track.filepath}"
                )
                return
        except Exception as e:
            logger.error(f"Failed to load track {track_id}: {e}")
            await self._send_error(websocket, track_id, str(e))
            return

        try:
            # Create processor for this track
            processor = self.chunked_processor_class(
                track_id=track_id,
                filepath=track.filepath,
                preset=preset,
                intensity=intensity,
            )

            logger.info(
                f"Starting audio stream: track={track_id}, preset={preset}, "
                f"intensity={intensity}, chunks={processor.total_chunks}"
            )

            # Send stream start message with metadata
            await self._send_stream_start(
                websocket,
                track_id=track_id,
                preset=preset,
                intensity=intensity,
                sample_rate=processor.sample_rate,
                channels=processor.channels,
                total_chunks=processor.total_chunks,
                chunk_duration=processor.chunk_duration,
                total_duration=processor.duration,
            )

            # Process and stream chunks
            for chunk_idx in range(processor.total_chunks):
                if websocket.client_state.name != "CONNECTED":
                    logger.info(f"WebSocket disconnected, stopping stream")
                    break

                try:
                    # Process chunk with fast-start for first chunk
                    await self._process_and_stream_chunk(
                        chunk_idx, processor, websocket, on_progress
                    )

                    # Progress update
                    if on_progress:
                        progress = ((chunk_idx + 1) / processor.total_chunks) * 100
                        await on_progress(track_id, progress, f"Processed chunk {chunk_idx + 1}")

                except Exception as chunk_error:
                    logger.error(
                        f"Failed to process chunk {chunk_idx}: {chunk_error}",
                        exc_info=True
                    )
                    await self._send_error(
                        websocket,
                        track_id,
                        f"Failed to process chunk {chunk_idx}: {chunk_error}",
                    )
                    return

            # Stream complete
            logger.info(f"Audio stream complete: track={track_id}")
            await self._send_stream_end(
                websocket,
                track_id=track_id,
                total_samples=int(processor.duration * processor.sample_rate),
                duration=processor.duration,
            )

        except Exception as e:
            logger.error(f"Audio streaming failed: {e}", exc_info=True)
            await self._send_error(websocket, track_id, str(e))

    async def _process_and_stream_chunk(
        self,
        chunk_index: int,
        processor,
        websocket: WebSocket,
        on_progress: Optional[Callable] = None,
    ) -> None:
        """
        Process single chunk and stream PCM samples to client.

        Args:
            chunk_index: Index of chunk to process (0-based)
            processor: ChunkedProcessor instance
            websocket: WebSocket connection to client
            on_progress: Optional progress callback
        """
        # Use fast-start for first chunk (process quickly)
        fast_start = chunk_index == 0

        logger.debug(
            f"Processing chunk {chunk_index}/{processor.total_chunks} "
            f"(fast_start={fast_start})"
        )

        # Process chunk - use async version directly and await it
        # This ensures the chunk file is created before we try to load it
        await processor.process_chunk_safe(chunk_index, fast_start=fast_start)

        # Load processed chunk from disk
        chunk_path = processor._get_chunk_path(chunk_index)
        try:
            from auralis.io.unified_loader import load_audio

            pcm_samples, sr = load_audio(str(chunk_path))

            logger.debug(
                f"Chunk {chunk_index}: loaded {len(pcm_samples)} samples at {sr}Hz"
            )

            # Stream PCM samples to client
            await self._send_pcm_chunk(
                websocket,
                pcm_samples=pcm_samples,
                chunk_index=chunk_index,
                total_chunks=processor.total_chunks,
                crossfade_samples=int(
                    processor.chunk_duration * processor.sample_rate
                ),  # Overlap duration
            )

        except Exception as e:
            logger.error(f"Failed to load/stream chunk {chunk_index}: {e}")
            raise

    async def _send_pcm_chunk(
        self,
        websocket: WebSocket,
        pcm_samples: np.ndarray,
        chunk_index: int,
        total_chunks: int,
        crossfade_samples: int,
    ) -> None:
        """
        Send PCM samples as audio_chunk message to client.

        Args:
            websocket: WebSocket connection
            pcm_samples: NumPy array of PCM samples (mono or stereo)
            chunk_index: Index of this chunk
            total_chunks: Total number of chunks
            crossfade_samples: Number of overlap samples at chunk boundary
        """
        # Ensure float32 for consistency
        if pcm_samples.dtype != np.float32:
            pcm_samples = pcm_samples.astype(np.float32)

        # Convert to base64 for JSON transmission
        import base64

        pcm_bytes = pcm_samples.tobytes()
        pcm_base64 = base64.b64encode(pcm_bytes).decode("ascii")

        message = {
            "type": "audio_chunk",
            "data": {
                "chunk_index": chunk_index,
                "chunk_count": total_chunks,
                "samples": pcm_base64,
                "sample_count": len(pcm_samples),
                "crossfade_samples": crossfade_samples,
            },
        }

        await websocket.send_text(json.dumps(message))
        logger.debug(
            f"Streamed chunk {chunk_index}: {len(pcm_samples)} samples "
            f"({len(pcm_base64) / 1024:.1f}KB base64)"
        )

    async def _send_stream_start(
        self,
        websocket: WebSocket,
        track_id: int,
        preset: str,
        intensity: float,
        sample_rate: int,
        channels: int,
        total_chunks: int,
        chunk_duration: float,
        total_duration: float,
    ) -> None:
        """Send audio_stream_start message to client."""
        message = {
            "type": "audio_stream_start",
            "data": {
                "track_id": track_id,
                "preset": preset,
                "intensity": intensity,
                "sample_rate": sample_rate,
                "channels": channels,
                "total_chunks": total_chunks,
                "chunk_duration": chunk_duration,
                "total_duration": total_duration,
            },
        }
        await websocket.send_text(json.dumps(message))
        logger.debug(f"Sent stream_start: {total_chunks} chunks, {total_duration}s duration")

    async def _send_stream_end(
        self,
        websocket: WebSocket,
        track_id: int,
        total_samples: int,
        duration: float,
    ) -> None:
        """Send audio_stream_end message to client."""
        message = {
            "type": "audio_stream_end",
            "data": {
                "track_id": track_id,
                "total_samples": total_samples,
                "duration": duration,
            },
        }
        await websocket.send_text(json.dumps(message))
        logger.debug(f"Sent stream_end: {total_samples} samples, {duration}s duration")

    async def _send_error(
        self, websocket: WebSocket, track_id: int, error_message: str
    ) -> None:
        """Send audio_stream_error message to client."""
        message = {
            "type": "audio_stream_error",
            "data": {
                "track_id": track_id,
                "error": error_message,
                "code": "STREAMING_ERROR",
            },
        }
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
