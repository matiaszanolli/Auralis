"""
MSE Streaming Router
~~~~~~~~~~~~~~~~~~~~

Provides Media Source Extensions (MSE) compatible progressive streaming.
Enables instant preset switching without buffering pauses.

Endpoints:
- GET /api/mse/stream/{track_id}/metadata - Get stream metadata for MSE initialization
- GET /api/mse/stream/{track_id}/chunk/{chunk_idx} - Stream individual audio chunk

Architecture:
- Integrates with multi-tier buffer for instant chunk delivery
- Serves 30-second WAV chunks compatible with MSE SourceBuffer
- Supports dynamic preset switching without playback interruption

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from typing import Optional
import logging
import os
import math
import time
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(tags=["mse-streaming"])


class StreamMetadata(BaseModel):
    """Metadata for MSE stream initialization"""
    track_id: int
    duration: float  # Total duration in seconds
    sample_rate: int
    channels: int
    chunk_duration: int  # Duration of each chunk in seconds
    total_chunks: int
    mime_type: str
    codecs: str


class ChunkMetadata(BaseModel):
    """Metadata for individual chunk"""
    chunk_idx: int
    start_time: float  # Start time in seconds
    end_time: float  # End time in seconds
    duration: float
    cache_tier: Optional[str] = None  # L1, L2, L3, or None (cache miss)
    latency_ms: Optional[float] = None


def create_mse_streaming_router(
    get_library_manager,
    get_multi_tier_buffer,
    chunked_audio_processor_class,
    chunk_duration: int = 30
):
    """
    Factory function to create MSE streaming router with dependencies.

    Args:
        get_library_manager: Callable that returns LibraryManager instance
        get_multi_tier_buffer: Callable that returns MultiTierBuffer instance
        chunked_audio_processor_class: ChunkedAudioProcessor class
        chunk_duration: Duration of each chunk in seconds (default: 30)

    Returns:
        APIRouter: Configured router instance
    """

    @router.get("/api/mse/stream/{track_id}/metadata", response_model=StreamMetadata)
    async def get_stream_metadata(track_id: int):
        """
        Get stream metadata for MSE initialization.

        This endpoint provides all information needed by the frontend to:
        - Create MediaSource and SourceBuffer
        - Calculate chunk indices for seek operations
        - Display progress and buffering state

        Args:
            track_id: Track ID from library

        Returns:
            StreamMetadata: Complete stream metadata

        Raises:
            HTTPException: If library not available or track not found
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library not available")

        try:
            # Get track from library
            track = library_manager.tracks.get_by_id(track_id)
            if not track:
                raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

            # Check if file exists
            if not os.path.exists(track.filepath):
                raise HTTPException(status_code=404, detail=f"Audio file not found: {track.filepath}")

            # Calculate total chunks
            duration = track.duration if hasattr(track, 'duration') and track.duration else 0
            if duration == 0:
                # Load audio to get duration
                try:
                    from auralis.io.unified_loader import load_audio
                    audio, sr = load_audio(track.filepath)
                    duration = len(audio) / sr
                except Exception as e:
                    logger.error(f"Failed to load audio for duration: {e}")
                    duration = 180  # Default to 3 minutes if loading fails

            total_chunks = math.ceil(duration / chunk_duration)

            metadata = StreamMetadata(
                track_id=track_id,
                duration=duration,
                sample_rate=44100,  # Standard output sample rate
                channels=2,  # Stereo output
                chunk_duration=chunk_duration,
                total_chunks=total_chunks,
                mime_type="audio/wav",
                codecs="pcm"  # PCM codec for WAV
            )

            logger.info(f"Stream metadata for track {track_id}: {total_chunks} chunks, {duration:.1f}s")
            return metadata

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get stream metadata: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get stream metadata: {e}")

    @router.get("/api/mse/stream/{track_id}/chunk/{chunk_idx}")
    async def stream_chunk(
        track_id: int,
        chunk_idx: int,
        preset: str = "adaptive",
        intensity: float = 1.0,
        enhanced: bool = True
    ):
        """
        Stream a single audio chunk for MSE playback.

        This is the core endpoint for progressive streaming. It:
        1. Checks multi-tier buffer for cached chunk (L1/L2/L3)
        2. Serves instantly if cache hit (0-200ms latency)
        3. Processes on-demand if cache miss (500ms-2s)

        The multi-tier buffer pre-processes chunks based on:
        - Current playback position (L1 cache)
        - Predicted preset switches (L2 cache)
        - Long-term buffer for current preset (L3 cache)

        Args:
            track_id: Track ID from library
            chunk_idx: Chunk index (0-based)
            preset: Processing preset (default: adaptive)
            intensity: Processing intensity 0.0-1.0 (default: 1.0)
            enhanced: Enable enhancement (default: True)

        Returns:
            Response: Audio chunk as WAV bytes with cache metadata headers

        Headers:
            - X-Chunk-Index: Chunk index
            - X-Cache-Tier: L1/L2/L3 (if cache hit) or MISS (if cache miss)
            - X-Latency-Ms: Latency in milliseconds
            - X-Preset: Applied preset
            - Content-Type: audio/wav

        Raises:
            HTTPException: If library not available, track not found, or processing fails
        """
        start_time = time.time()

        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library not available")

        multi_tier_buffer = get_multi_tier_buffer()

        try:
            # Get track from library
            track = library_manager.tracks.get_by_id(track_id)
            if not track:
                raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

            # Check if file exists
            if not os.path.exists(track.filepath):
                raise HTTPException(status_code=404, detail=f"Audio file not found: {track.filepath}")

            # Initialize response variables
            cache_tier = None
            audio_bytes = None

            # If enhancement disabled, serve original audio chunk
            if not enhanced:
                logger.info(f"Serving original (unenhanced) chunk {chunk_idx} for track {track_id}")
                audio_bytes = await _get_original_chunk(track.filepath, chunk_idx, chunk_duration)
                cache_tier = "ORIGINAL"
            else:
                # Try multi-tier buffer first (if available)
                if multi_tier_buffer:
                    try:
                        # Check cache tiers (L1 → L2 → L3)
                        chunk_data = await multi_tier_buffer.get_chunk(
                            track_id=track_id,
                            preset=preset,
                            chunk_idx=chunk_idx,
                            intensity=intensity
                        )

                        if chunk_data:
                            # Cache hit! 🎉
                            cache_tier = chunk_data.get("tier", "UNKNOWN")
                            audio_bytes = chunk_data.get("audio_bytes")
                            logger.info(f"✅ Cache HIT: {cache_tier} cache for track {track_id}, chunk {chunk_idx}, preset {preset}")
                    except Exception as e:
                        logger.warning(f"Multi-tier buffer query failed: {e}")

                # Cache miss - process on demand
                if audio_bytes is None:
                    cache_tier = "MISS"
                    logger.info(f"❌ Cache MISS: Processing chunk {chunk_idx} on-demand for track {track_id}, preset {preset}")

                    if chunked_audio_processor_class is None:
                        raise HTTPException(
                            status_code=503,
                            detail="Chunked audio processor not available"
                        )

                    # Create processor
                    processor = chunked_audio_processor_class(
                        track_id=track_id,
                        filepath=track.filepath,
                        preset=preset,
                        intensity=intensity,
                        chunk_cache={}  # Use empty cache, let multi-tier buffer handle caching
                    )

                    # Process single chunk
                    chunk_path = processor.process_chunk(chunk_idx)

                    # Read chunk data
                    if not os.path.exists(chunk_path):
                        raise HTTPException(
                            status_code=500,
                            detail=f"Chunk processing failed: output file not found"
                        )

                    # Read chunk as bytes
                    with open(chunk_path, "rb") as f:
                        audio_bytes = f.read()

                    logger.info(f"Chunk {chunk_idx} processed on-demand: {len(audio_bytes)} bytes")

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Log performance
            logger.info(f"Chunk {chunk_idx} delivered: {cache_tier} cache, {latency_ms:.1f}ms latency")

            # Return audio chunk with metadata headers
            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={
                    "X-Chunk-Index": str(chunk_idx),
                    "X-Cache-Tier": cache_tier,
                    "X-Latency-Ms": f"{latency_ms:.1f}",
                    "X-Preset": preset,
                    "X-Enhanced": "true" if enhanced else "false",
                    "Content-Length": str(len(audio_bytes)),
                    # MSE compatibility headers
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "no-cache"  # Don't let browser cache chunks
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Chunk streaming failed after {latency_ms:.1f}ms: {e}")
            raise HTTPException(status_code=500, detail=f"Chunk streaming failed: {e}")

    async def _get_original_chunk(
        filepath: str,
        chunk_idx: int,
        chunk_duration: int
    ) -> bytes:
        """
        Extract a chunk from original audio file without processing.

        Args:
            filepath: Path to audio file
            chunk_idx: Chunk index
            chunk_duration: Chunk duration in seconds

        Returns:
            bytes: WAV chunk data
        """
        from auralis.io.unified_loader import load_audio
        from auralis.io.saver import save
        import tempfile

        # Load audio
        audio, sr = load_audio(filepath)

        # Calculate chunk boundaries
        start_sample = chunk_idx * chunk_duration * sr
        end_sample = min((chunk_idx + 1) * chunk_duration * sr, len(audio))

        # Extract chunk
        chunk_audio = audio[int(start_sample):int(end_sample)]

        # Save chunk to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            save(tmp_path, chunk_audio, sr, subtype='PCM_16')

            # Read bytes
            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()

            return audio_bytes
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    return router
