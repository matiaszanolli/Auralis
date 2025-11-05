"""
WebM/Opus Unified Streaming Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Simplified unified streaming architecture that ALWAYS serves WebM/Opus format.
Processing happens client-side using Web Audio API.

This eliminates the dual MSE/HTML5 Audio architecture complexity while maintaining
all the benefits:
- Multi-tier buffer caching (L1/L2/L3) for instant delivery
- Progressive streaming for fast playback start
- Client-side DSP processing for real-time preset switching
- 86% smaller file sizes vs WAV (WebM/Opus @ 192kbps)
- 50-100x real-time encoding speed

Architecture:
  1. Backend always returns WebM/Opus chunks (cached or encoded on-demand)
  2. Frontend decodes WebM to AudioBuffer using Web Audio API
  3. Frontend applies DSP processing client-side if enhancement enabled
  4. Single player, single buffer, zero dual-player conflicts

:copyright: (C) 2025 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import APIRouter, HTTPException, Response, Query
from pydantic import BaseModel
from typing import Optional
import logging
import os
import math
import time
import numpy as np
from pathlib import Path

# Import WebM encoder
from encoding.webm_encoder import encode_to_webm_opus, WebMEncoderError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webm-streaming"])


class StreamMetadata(BaseModel):
    """Metadata for WebM stream initialization"""
    track_id: int
    duration: float  # Total duration in seconds
    sample_rate: int
    channels: int
    chunk_duration: int  # Duration of each chunk in seconds
    total_chunks: int
    mime_type: str  # Always "audio/webm"
    codecs: str  # Always "opus"
    format_version: str  # Unified architecture version


def create_webm_streaming_router(
    get_library_manager,
    get_multi_tier_buffer,
    chunked_audio_processor_class,
    chunk_duration: int = 30
):
    """
    Factory function to create unified WebM streaming router with dependencies.

    This is the new simplified architecture that replaces both MSE and MTB routers.

    Args:
        get_library_manager: Callable that returns LibraryManager instance
        get_multi_tier_buffer: Callable that returns MultiTierBuffer instance
        chunked_audio_processor_class: ChunkedAudioProcessor class (now outputs WebM)
        chunk_duration: Duration of each chunk in seconds (default: 30)

    Returns:
        APIRouter: Configured router instance
    """

    @router.get("/api/stream/{track_id}/metadata", response_model=StreamMetadata)
    async def get_stream_metadata(track_id: int):
        """
        Get stream metadata for player initialization.

        This endpoint provides all information needed by the frontend to:
        - Initialize UnifiedWebMAudioPlayer
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
                mime_type="audio/webm",
                codecs="opus",
                format_version="unified-v1.0"
            )

            logger.info(f"Stream metadata for track {track_id}: {total_chunks} chunks, {duration:.1f}s, WebM/Opus")
            return metadata

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get stream metadata: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get stream metadata: {e}")

    @router.get("/api/stream/{track_id}/chunk/{chunk_idx}")
    async def stream_chunk(
        track_id: int,
        chunk_idx: int,
        preset: str = Query("adaptive", description="Processing preset (for cache key)"),
        intensity: float = Query(1.0, ge=0.0, le=1.0, description="Processing intensity (for cache key)"),
        enhanced: bool = Query(True, description="Whether enhancement was requested (for cache key)")
    ):
        """
        Stream a single WebM/Opus audio chunk.

        IMPORTANT: This endpoint ALWAYS returns WebM/Opus format.
        Processing happens CLIENT-SIDE using Web Audio API.

        The backend serves two types of chunks:
        1. Enhanced chunks: Processed audio encoded to WebM (from ChunkedAudioProcessor)
        2. Original chunks: Unprocessed audio encoded to WebM (direct from source file)

        Multi-tier buffer caching provides instant delivery:
        - L1 cache: Currently playing chunk (instant, 0-10ms)
        - L2 cache: Next predicted chunk (fast, 10-50ms)
        - L3 cache: Background buffer (moderate, 50-200ms)
        - Cache miss: On-demand processing (slow, 500ms-2s)

        Args:
            track_id: Track ID from library
            chunk_idx: Chunk index (0-based)
            preset: Processing preset (for cache key only, not applied here)
            intensity: Processing intensity (for cache key only)
            enhanced: Whether this is an enhanced chunk (for cache key)

        Returns:
            Response: Audio chunk as WebM/Opus bytes with cache metadata headers

        Headers:
            - X-Chunk-Index: Chunk index
            - X-Cache-Tier: L1/L2/L3/MISS/ORIGINAL
            - X-Latency-Ms: Latency in milliseconds
            - X-Enhanced: true/false (was this chunk processed)
            - X-Preset: Applied preset (if enhanced)
            - Content-Type: audio/webm; codecs=opus

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
            webm_bytes = None

            # If enhancement disabled, serve original audio chunk
            if not enhanced:
                logger.info(f"Serving original (unenhanced) chunk {chunk_idx} for track {track_id}")
                webm_bytes = await _get_original_webm_chunk(track.filepath, chunk_idx, chunk_duration)
                cache_tier = "ORIGINAL"
            else:
                # Streamlined cache integration (Beta.9)
                cached_chunk_path = None
                cache_tier = "MISS"

                # Try to get chunk from streamlined cache
                if multi_tier_buffer:
                    try:
                        cached_chunk_path, tier = await multi_tier_buffer.get_chunk(
                            track_id=track_id,
                            chunk_idx=chunk_idx,
                            preset=preset,
                            intensity=intensity
                        )
                        if cached_chunk_path and os.path.exists(cached_chunk_path):
                            cache_tier = tier.upper()
                            logger.info(f"✅ Cache {tier.upper()} HIT: Serving chunk {chunk_idx} from cache")

                            # Read cached chunk
                            with open(cached_chunk_path, 'rb') as f:
                                webm_bytes = f.read()
                        else:
                            cache_tier = "MISS"
                    except Exception as e:
                        logger.warning(f"Cache lookup failed: {e}, falling back to on-demand processing")
                        cache_tier = "MISS"

                # Cache miss - process on demand
                if cache_tier == "MISS":
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

                    # Get WebM/Opus chunk (processor now outputs WebM directly)
                    webm_chunk_path = processor.get_webm_chunk_path(chunk_idx)

                    # Read chunk data
                    if not os.path.exists(webm_chunk_path):
                        raise HTTPException(
                            status_code=500,
                            detail=f"Chunk processing failed: WebM output file not found"
                        )

                    # Read WebM/Opus chunk bytes
                    try:
                        with open(webm_chunk_path, 'rb') as f:
                            webm_bytes = f.read()

                        logger.info(f"Chunk {chunk_idx} processed on-demand: {len(webm_bytes)} bytes WebM/Opus")

                        # Add to streamlined cache (Tier 1 or Tier 2 auto-detected)
                        if multi_tier_buffer and webm_chunk_path:
                            try:
                                # Get track duration for cache planning
                                import mutagen
                                audio_file = mutagen.File(track.filepath)
                                track_duration = audio_file.info.length if audio_file else None

                                # Update position for cache tier detection
                                await multi_tier_buffer.update_position(
                                    track_id=track_id,
                                    position=chunk_idx * chunk_duration,
                                    preset=preset,
                                    intensity=intensity,
                                    track_duration=track_duration
                                )

                                # Add chunk to cache (tier auto-detected based on position)
                                await multi_tier_buffer.add_chunk(
                                    track_id=track_id,
                                    chunk_idx=chunk_idx,
                                    chunk_path=Path(webm_chunk_path),
                                    preset=preset,
                                    intensity=intensity,
                                    tier="auto"  # Auto-detect Tier 1 vs Tier 2
                                )
                                logger.debug(f"Added chunk {chunk_idx} to streamlined cache")
                            except Exception as cache_err:
                                logger.warning(f"Failed to add chunk to cache: {cache_err}")

                    except Exception as e:
                        logger.error(f"WebM chunk read failed for chunk {chunk_idx}: {e}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Chunk read failed: {str(e)}"
                        )

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Log performance
            logger.info(f"Chunk {chunk_idx} delivered: {cache_tier} cache, {latency_ms:.1f}ms latency, WebM/Opus")

            # Return audio chunk with metadata headers
            return Response(
                content=webm_bytes,
                media_type="audio/webm; codecs=opus",
                headers={
                    "X-Chunk-Index": str(chunk_idx),
                    "X-Cache-Tier": cache_tier,
                    "X-Latency-Ms": f"{latency_ms:.1f}",
                    "X-Enhanced": "true" if enhanced else "false",
                    "X-Preset": preset if enhanced else "none",
                    "Content-Length": str(len(webm_bytes)),
                    # Progressive streaming compatibility headers
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "no-cache"  # Don't let browser cache chunks
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            import traceback
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Chunk streaming failed after {latency_ms:.1f}ms: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Chunk streaming failed: {e}")

    async def _get_original_webm_chunk(
        filepath: str,
        chunk_idx: int,
        chunk_duration: int
    ) -> bytes:
        """
        Extract a chunk from original audio file without processing.
        Returns WebM/Opus encoded audio.

        This is used when enhancement is disabled (enhanced=False).

        Args:
            filepath: Path to audio file
            chunk_idx: Chunk index
            chunk_duration: Chunk duration in seconds

        Returns:
            bytes: WebM/Opus chunk data

        Raises:
            WebMEncoderError: If encoding fails
        """
        from auralis.io.unified_loader import load_audio

        # Load audio chunk
        audio, sr = load_audio(filepath)

        # Calculate chunk boundaries
        start_sample = chunk_idx * chunk_duration * sr
        end_sample = min((chunk_idx + 1) * chunk_duration * sr, len(audio))

        # Extract chunk
        chunk_audio = audio[int(start_sample):int(end_sample)]

        # Encode directly to WebM/Opus
        try:
            webm_bytes = encode_to_webm_opus(
                chunk_audio,
                sr,
                bitrate=192,  # High quality (transparent)
                vbr=True,
                compression_level=10,
                application='audio'
            )
            logger.info(f"Original chunk {chunk_idx} encoded to WebM: {len(webm_bytes)} bytes")
            return webm_bytes

        except WebMEncoderError as e:
            logger.error(f"WebM encoding failed for original chunk {chunk_idx}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"WebM encoding failed: {str(e)}"
            )

    return router
