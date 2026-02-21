"""
WAV Audio Unified Streaming Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Simplified unified streaming architecture that serves WAV format for browser compatibility.
Processing happens client-side using Web Audio API.

Web Audio API's decodeAudioData() only supports: WAV, MP3, Ogg Vorbis, FLAC (NOT WebM).
This simplified architecture uses WAV for universal browser support.

All benefits maintained:
- Multi-tier buffer caching (L1/L2/L3) for instant delivery
- Progressive streaming for fast playback start
- Client-side DSP processing for real-time preset switching
- Universal browser codec support (no decoder library needed)
- Simple format encoding (minimal processing)

Architecture:
  1. Backend always returns WAV chunks (cached or encoded on-demand)
  2. Frontend decodes WAV to AudioBuffer using Web Audio API (native support)
  3. Frontend applies DSP processing client-side if enhancement enabled
  4. Single player, single buffer, zero dual-player conflicts

:copyright: (C) 2025 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import math
import os
import time
from pathlib import Path
from typing import Any
from collections.abc import Callable

# Import WAV encoder (replacing WebM for browser compatibility)
from encoding.wav_encoder import WAVEncoderError, encode_to_wav
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from .dependencies import require_repository_factory

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webm-streaming"])


class StreamMetadata(BaseModel):
    """Metadata for WAV stream initialization"""
    track_id: int
    duration: float  # Total duration in seconds
    sample_rate: int
    channels: int
    chunk_duration: int  # Duration of each chunk in seconds (actual chunk length)
    chunk_interval: int  # Interval between chunk starts in seconds (for indexing)
    total_chunks: int
    mime_type: str  # Always "audio/wav"
    codecs: str  # Always "PCM_16"
    format_version: str  # Unified architecture version
    # NEW: Actual playable duration for each chunk type
    # Chunk 0: full duration (chunk_duration)
    # Chunks 1+: interval duration (chunk_interval), overlap already trimmed
    chunk_playable_duration: int  # Playable duration in seconds for non-first chunks
    overlap_duration: int  # Overlap between chunks for reference


def create_webm_streaming_router(
    get_multi_tier_buffer: Callable[[], Any],
    chunked_audio_processor_class: Any,
    chunk_duration: int = 10,
    chunk_interval: int = 10,
    get_repository_factory: Callable[[], Any] | None = None
) -> APIRouter:
    """
    Factory function to create unified WebM streaming router with dependencies.

    This is the new simplified architecture that replaces both MSE and MTB routers.

    Args:
        get_multi_tier_buffer: Callable that returns MultiTierBuffer instance
        chunked_audio_processor_class: ChunkedAudioProcessor class (now outputs WebM)
        chunk_duration: Duration of each chunk in seconds (default: 10, reduced from 30s for Phase 2)
        chunk_interval: Interval between chunk starts in seconds (default: 10, same as duration for no overlap)
        get_repository_factory: Callable that returns RepositoryFactory instance

    Returns:
        APIRouter: Configured router instance

    Note:
        Phase 6B: Fully migrated to RepositoryFactory pattern (no LibraryManager fallback)
    """

    def get_repos() -> Any:
        """Get repository factory for accessing repositories."""
        if get_repository_factory is None:
            raise ValueError("Repository factory not configured")
        return require_repository_factory(get_repository_factory)

    @router.get("/api/stream/{track_id}/metadata", response_model=StreamMetadata)
    async def get_stream_metadata(track_id: int) -> StreamMetadata:
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
        try:
            repos = get_repos()
            # Get track from library
            track = repos.tracks.get_by_id(track_id)
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

            # Calculate total chunks based on interval (not duration) for overlap model
            # With 15s chunks and 10s intervals: chunks start at 0s, 10s, 20s, etc.
            total_chunks = math.ceil(duration / chunk_interval)

            # Get actual sample rate from audio file without loading full audio
            try:
                from auralis.io.unified_loader import get_audio_info
                audio_info = get_audio_info(track.filepath)
                actual_sr = audio_info.get('sample_rate', 44100)
                actual_channels = audio_info.get('channels', 2)
            except Exception as e:
                logger.warning(f"Failed to get audio info, using 44100Hz/stereo default: {e}")
                actual_sr = 44100
                actual_channels = 2

            metadata = StreamMetadata(
                track_id=track_id,
                duration=duration,
                sample_rate=actual_sr,  # Actual sample rate from audio file
                channels=actual_channels,  # Actual channels from audio file
                chunk_duration=chunk_duration,
                chunk_interval=chunk_interval,
                total_chunks=total_chunks,
                mime_type="audio/wav",
                codecs="PCM_16",
                format_version="unified-v1.0",
                chunk_playable_duration=chunk_interval,  # Non-first chunks play for interval duration
                overlap_duration=5  # 5s overlap between chunks (context trimmed at backend)
            )

            logger.info(f"Stream metadata for track {track_id}: {total_chunks} chunks, {duration:.1f}s, "
                       f"chunk_duration={chunk_duration}s, chunk_interval={chunk_interval}s, WAV/PCM")
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
    ) -> Response:
        """
        Stream a single WAV audio chunk.

        IMPORTANT: This endpoint ALWAYS returns WAV format (browser-compatible with Web Audio API).
        Processing happens CLIENT-SIDE using Web Audio API.

        The backend serves two types of chunks:
        1. Enhanced chunks: Processed audio encoded to WAV (from ChunkedAudioProcessor)
        2. Original chunks: Unprocessed audio encoded to WAV (direct from source file)

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
            Response: Audio chunk as WAV bytes with cache metadata headers

        Headers:
            - X-Chunk-Index: Chunk index
            - X-Cache-Tier: L1/L2/L3/MISS/ORIGINAL
            - X-Latency-Ms: Latency in milliseconds
            - X-Enhanced: true/false (was this chunk processed)
            - X-Preset: Applied preset (if enhanced)
            - Content-Type: audio/wav

        Raises:
            HTTPException: If library not available, track not found, or processing fails
        """
        start_time = time.time()

        multi_tier_buffer = get_multi_tier_buffer()

        try:
            repos = get_repos()
            # Get track from library
            track = repos.tracks.get_by_id(track_id)
            if not track:
                raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

            # Check if file exists
            if not os.path.exists(track.filepath):
                raise HTTPException(status_code=404, detail=f"Audio file not found: {track.filepath}")

            # Initialize response variables
            cache_tier = None
            wav_bytes = None

            # If enhancement disabled, serve original audio chunk
            if not enhanced:
                logger.info(f"Serving original (unenhanced) chunk {chunk_idx} for track {track_id}")
                wav_bytes = await _get_original_wav_chunk(track.filepath, chunk_idx, chunk_duration, chunk_interval)
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

                            # Read cached chunk (offloaded to thread with timeout — fixes #2329)
                            wav_bytes = await asyncio.wait_for(
                                asyncio.to_thread(Path(cached_chunk_path).read_bytes),
                                timeout=10.0
                            )
                        else:
                            cache_tier = "MISS"
                    except Exception as e:
                        logger.warning(f"Cache lookup failed: {e}, falling back to on-demand processing")
                        cache_tier = "MISS"

                # Cache miss - process on demand using ChunkedAudioProcessor for enhancement
                if cache_tier == "MISS":
                    logger.info(f"❌ Cache MISS: Processing chunk {chunk_idx} on-demand for track {track_id}, preset {preset}")

                    # Use ChunkedAudioProcessor to handle enhancement with proper DSP
                    # Wrap instantiation in timeout to prevent hangs on corrupt/slow files (#2125)
                    try:
                        processor = await asyncio.wait_for(
                            asyncio.to_thread(
                                chunked_audio_processor_class,
                                track_id=track_id,
                                filepath=track.filepath,
                                preset=preset,
                                intensity=intensity
                            ),
                            timeout=30.0
                        )
                    except TimeoutError:
                        logger.error(f"Processor instantiation timed out for track {track_id} (30s)")
                        raise HTTPException(
                            status_code=500,
                            detail="Audio processor initialization timed out. File may be corrupt or on slow storage."
                        )

                    # Get the WAV chunk path directly from the processor
                    # This applies enhancement via HybridProcessor if preset is not None
                    chunk_path = processor.get_wav_chunk_path(chunk_idx)

                    try:
                        # Read the processed chunk (offloaded to thread with timeout — fixes #2329)
                        wav_bytes = await asyncio.wait_for(
                            asyncio.to_thread(Path(chunk_path).read_bytes),
                            timeout=10.0
                        )
                        logger.info(f"Chunk {chunk_idx} processed on-demand: {len(wav_bytes)} bytes WAV at {processor.sample_rate}Hz")

                        # Add to streamlined cache (Tier 1 or Tier 2 auto-detected)
                        if multi_tier_buffer:
                            try:
                                # Get track duration for cache planning
                                import mutagen
                                audio_file = mutagen.File(track.filepath)  # type: ignore[attr-defined]
                                track_duration: float | None = audio_file.info.length if audio_file else None

                                # Update position for cache tier detection
                                await multi_tier_buffer.update_position(
                                    track_id=track_id,
                                    position=chunk_idx * chunk_duration,
                                    preset=preset,
                                    intensity=intensity,
                                    track_duration=track_duration
                                )

                                # Add chunk to cache (tier auto-detected based on position)
                                # Note: Caching WAV bytes would require writing to temp file first
                                logger.debug(f"Skipping cache for on-demand WAV chunk {chunk_idx}")
                            except Exception as cache_err:
                                logger.warning(f"Failed to update cache position: {cache_err}")

                    except Exception as e:
                        logger.error(f"Failed to process chunk {chunk_idx}: {e}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Chunk processing failed: {str(e)}"
                        )

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Log performance
            logger.info(f"Chunk {chunk_idx} delivered: {cache_tier} cache, {latency_ms:.1f}ms latency, WAV/PCM")

            # Return audio chunk with metadata headers
            if wav_bytes is None:
                raise HTTPException(status_code=500, detail="Failed to generate audio chunk")

            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={
                    "X-Chunk-Index": str(chunk_idx),
                    "X-Cache-Tier": cache_tier,
                    "X-Latency-Ms": f"{latency_ms:.1f}",
                    "X-Enhanced": "true" if enhanced else "false",
                    "X-Preset": preset if enhanced else "none",
                    "Content-Length": str(len(wav_bytes)),
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

    async def _get_original_wav_chunk(
        filepath: str,
        chunk_idx: int,
        chunk_duration: int,
        chunk_interval: int
    ) -> bytes:
        """
        Extract a chunk from original audio file without processing.
        Returns WAV encoded audio (browser-compatible with Web Audio API).

        This is used when enhancement is disabled (enhanced=False).

        Args:
            filepath: Path to audio file
            chunk_idx: Chunk index
            chunk_duration: Chunk duration in seconds (actual length of chunk)
            chunk_interval: Interval between chunk starts in seconds (for overlap calculation)

        Returns:
            bytes: WAV chunk data

        Raises:
            WAVEncoderError: If encoding fails
        """
        from auralis.io.unified_loader import load_audio

        # Load audio (file I/O — run in thread to avoid blocking event loop)
        audio, sr = await asyncio.to_thread(load_audio, filepath)

        # Calculate chunk boundaries using chunk_interval for start position
        # With 10s chunks and 10s interval: chunk 0 starts at 0s, chunk 1 at 10s, chunk 2 at 20s, etc.
        chunk_start_time = chunk_idx * chunk_interval
        chunk_end_time = chunk_start_time + chunk_duration

        start_sample = int(chunk_start_time * sr)
        end_sample = min(int(chunk_end_time * sr), len(audio))

        # Extract chunk
        chunk_audio = audio[start_sample:end_sample]

        # Validate chunk has audio data
        if len(chunk_audio) == 0:
            logger.error(f"Original chunk {chunk_idx} extraction resulted in empty audio")
            logger.error(f"  Audio length: {len(audio)} samples")
            logger.error(f"  Chunk bounds: {start_sample}-{end_sample}")
            logger.error(f"  Time bounds: {chunk_start_time}s-{chunk_end_time}s")
            logger.error(f"  Sample rate: {sr}")
            raise HTTPException(
                status_code=400,
                detail=f"Chunk {chunk_idx} extraction resulted in empty audio"
            )

        logger.info(f"Original chunk {chunk_idx} extracted: {len(chunk_audio)} samples ({len(chunk_audio)/sr:.2f}s)")

        # Encode directly to WAV
        try:
            wav_bytes = await asyncio.to_thread(encode_to_wav, chunk_audio, sr)
            logger.info(f"Original chunk {chunk_idx} encoded to WAV: {len(wav_bytes)} bytes")
            return wav_bytes

        except WAVEncoderError as e:
            logger.error(f"WAV encoding failed for original chunk {chunk_idx}: {e}")
            logger.error(f"Chunk audio shape: {chunk_audio.shape}, dtype: {chunk_audio.dtype}")
            raise HTTPException(
                status_code=500,
                detail=f"WAV encoding failed: {str(e)}"
            )

    return router
