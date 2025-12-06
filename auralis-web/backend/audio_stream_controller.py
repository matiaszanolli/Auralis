#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Audio Stream Controller
~~~~~~~~~~~~~~~~~~~~~~~

Manages real-time audio streaming via WebSocket for enhanced audio playback.
Unified architecture: single WebSocket endpoint for all audio streaming.

Handles:
- Loading tracks and creating ChunkedProcessor instances
- Processing chunks on-demand with fast-start optimization
- Streaming PCM samples to connected WebSocket clients
- Managing crossfading at chunk boundaries
- Caching processed chunks to avoid reprocessing
- Error handling and recovery

Features:
- Multi-tier chunk caching (in-memory cache for recent processing)
- Fast-start optimization for first chunk (priority processing)
- Real-time progress callbacks via WebSocket
- Graceful error recovery and client disconnection handling

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
import numpy as np
import logging
import hashlib
from pathlib import Path
from typing import Optional, Callable, Tuple, Union, Dict, Any, Type
from fastapi import WebSocket
from collections import OrderedDict

from auralis.library import LibraryManager
from backend.cache import StreamlinedCacheManager, StreamlinedCacheAdapter
from backend.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger(__name__)


class SimpleChunkCache:
    """Simple in-memory cache for processed audio chunks."""

    def __init__(self, max_chunks: int = 50) -> None:
        """
        Initialize chunk cache.

        Args:
            max_chunks: Maximum number of chunks to keep in memory
        """
        self.cache: OrderedDict[str, Tuple[np.ndarray, int]] = OrderedDict()
        self.max_chunks: int = max_chunks

    def _make_key(self, track_id: int, chunk_idx: int, preset: str, intensity: float) -> str:
        """Generate cache key from parameters."""
        key_str = f"{track_id}:{chunk_idx}:{preset}:{intensity:.2f}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(
        self,
        track_id: int,
        chunk_idx: int,
        preset: str,
        intensity: float
    ) -> Optional[Tuple[np.ndarray, int]]:
        """
        Get chunk from cache.

        Returns:
            Tuple of (audio_samples, sample_rate) or None if not cached
        """
        key = self._make_key(track_id, chunk_idx, preset, intensity)
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
        sample_rate: int
    ) -> None:
        """Store chunk in cache."""
        key = self._make_key(track_id, chunk_idx, preset, intensity)

        # Remove oldest if at capacity
        if len(self.cache) >= self.max_chunks:
            removed_key = next(iter(self.cache))
            del self.cache[removed_key]
            logger.debug(f"Cache evicted oldest chunk to make space")

        self.cache[key] = (audio, sample_rate)
        logger.debug(f"✅ Cached chunk {chunk_idx}, preset {preset}, cache size: {len(self.cache)}")

    def clear(self) -> None:
        """Clear all cached chunks."""
        self.cache.clear()


class AudioStreamController:
    """
    Manages real-time audio streaming via WebSocket.

    Unified architecture: single WebSocket endpoint for all audio streaming.

    Streams processed audio chunks as PCM samples to frontend for playback.
    Handles fast-start optimization (first chunk processed quickly),
    crossfading at boundaries, caching for performance, and error recovery.
    """

    def __init__(
        self,
        chunked_processor_class: Optional[Type[ChunkedAudioProcessor]] = None,
        library_manager: Optional[LibraryManager] = None,
        cache_manager: Optional[Union[StreamlinedCacheManager, StreamlinedCacheAdapter, SimpleChunkCache]] = None
    ) -> None:
        """
        Initialize AudioStreamController.

        Args:
            chunked_processor_class: ChunkedAudioProcessor class for processing
            library_manager: LibraryManager instance for track lookup
            cache_manager: Optional cache manager for chunk caching.
                          If StreamlinedCacheManager, will be automatically wrapped with adapter.
        """
        self.chunked_processor_class: Optional[Type[ChunkedAudioProcessor]] = chunked_processor_class
        self.library_manager: Optional[LibraryManager] = library_manager

        # Wrap StreamlinedCacheManager with adapter for compatibility
        if isinstance(cache_manager, StreamlinedCacheManager):
            self.cache_manager: Union[StreamlinedCacheAdapter, SimpleChunkCache] = StreamlinedCacheAdapter(cache_manager)
            logger.info("StreamlinedCacheManager wrapped with StreamlinedCacheAdapter")
        else:
            self.cache_manager = cache_manager or SimpleChunkCache()

        self.active_streams: Dict[int, Any] = {}  # track_id -> streaming task

    async def stream_enhanced_audio(
        self,
        track_id: int,
        preset: str,
        intensity: float,
        websocket: WebSocket,
        on_progress: Optional[Callable[[int, float, str], Any]] = None
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
            processor: ChunkedAudioProcessor = self.chunked_processor_class(
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
        processor: ChunkedAudioProcessor,
        websocket: WebSocket,
        on_progress: Optional[Callable[[int, float, str], Any]] = None,
    ) -> None:
        """
        Process single chunk and stream PCM samples to client.

        Implements caching to avoid reprocessing chunks with same parameters.

        Args:
            chunk_index: Index of chunk to process (0-based)
            processor: ChunkedProcessor instance
            websocket: WebSocket connection to client
            on_progress: Optional progress callback
        """
        # Use fast-start for first chunk (process quickly)
        fast_start: bool = chunk_index == 0

        logger.debug(
            f"Processing chunk {chunk_index}/{processor.total_chunks} "
            f"(fast_start={fast_start})"
        )

        # Try to get from cache first
        pcm_samples: Optional[np.ndarray] = None
        sr: Optional[int] = None
        cache_hit: bool = False

        try:
            cached_result: Optional[Tuple[np.ndarray, int]] = self.cache_manager.get(
                track_id=processor.track_id,
                chunk_idx=chunk_index,
                preset=processor.preset,
                intensity=processor.intensity
            )
            if cached_result:
                pcm_samples, sr = cached_result
                cache_hit = True
                logger.info(f"✅ Cache HIT: chunk {chunk_index}, preset {processor.preset}")
        except Exception as e:
            logger.debug(f"Cache lookup failed (not critical): {e}")

        # Process chunk if not cached
        if not cache_hit:
            logger.debug(f"❌ Cache MISS: Processing chunk {chunk_index}")
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

                # Store in cache for future use
                try:
                    self.cache_manager.put(
                        track_id=processor.track_id,
                        chunk_idx=chunk_index,
                        preset=processor.preset,
                        intensity=processor.intensity,
                        audio=pcm_samples,
                        sample_rate=sr
                    )
                except Exception as e:
                    logger.debug(f"Failed to cache chunk (not critical): {e}")

            except Exception as e:
                logger.error(f"Failed to load chunk {chunk_index}: {e}")
                raise

        # Stream PCM samples to client
        try:
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
            logger.error(f"Failed to stream chunk {chunk_index}: {e}")
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

        Splits large PCM data into multiple messages if needed (WebSocket
        client library has 1MB frame limit, so we split at ~500KB per message).

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

        # Split into smaller frames to avoid WebSocket client 1MB limit
        # Each float32 sample = 4 bytes. Base64 encodes to 4/3 size.
        # Target: ~400KB base64 per message (safe margin below 1MB limit)
        TARGET_BASE64_SIZE: int = 400 * 1024  # 400 KB
        BYTES_PER_SAMPLE: int = 4  # float32
        samples_per_frame: int = int(TARGET_BASE64_SIZE / (BYTES_PER_SAMPLE * 4/3))

        total_samples: int = len(pcm_samples)
        num_frames: int = (total_samples + samples_per_frame - 1) // samples_per_frame

        for frame_idx in range(num_frames):
            start_idx: int = frame_idx * samples_per_frame
            end_idx: int = min(start_idx + samples_per_frame, total_samples)
            frame_samples: np.ndarray = pcm_samples[start_idx:end_idx]

            pcm_bytes: bytes = frame_samples.tobytes()
            pcm_base64: str = base64.b64encode(pcm_bytes).decode("ascii")

            message: Dict[str, Any] = {
                "type": "audio_chunk",
                "data": {
                    "chunk_index": chunk_index,
                    "chunk_count": total_chunks,
                    "frame_index": frame_idx,
                    "frame_count": num_frames,
                    "samples": pcm_base64,
                    "sample_count": len(frame_samples),
                    "crossfade_samples": crossfade_samples if frame_idx == 0 else 0,
                },
            }

            await websocket.send_text(json.dumps(message))
            logger.debug(
                f"Streamed chunk {chunk_index} frame {frame_idx}/{num_frames}: "
                f"{len(frame_samples)} samples ({len(pcm_base64) / 1024:.1f}KB base64)"
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
        message: Dict[str, Any] = {
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
        message: Dict[str, Any] = {
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
        self,
        websocket: WebSocket,
        track_id: int,
        error_message: str
    ) -> None:
        """Send audio_stream_error message to client."""
        message: Dict[str, Any] = {
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
