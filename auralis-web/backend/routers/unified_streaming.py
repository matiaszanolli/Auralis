"""
Unified Streaming Router
~~~~~~~~~~~~~~~~~~~~~~~~~

Single unified endpoint that intelligently routes between:
- MSE Progressive Streaming (unenhanced mode) - instant preset switching
- Multi-Tier Buffer System (enhanced mode) - intelligent L1/L2/L3 caching

This eliminates dual playback conflicts while providing the best of both systems.

:copyright: (C) 2025 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import logging
import math
import time
from pathlib import Path
import librosa

# Import encoder at module level for testability
try:
    from webm_encoder import encode_audio_to_webm, get_encoder
except ImportError:
    # Graceful fallback if encoder not available
    encode_audio_to_webm = None
    get_encoder = None

logger = logging.getLogger(__name__)

router = APIRouter(tags=["unified-streaming"])


class StreamMetadata(BaseModel):
    """Metadata for unified stream initialization"""
    track_id: int
    duration: float
    total_chunks: int
    chunk_duration: float
    format: str
    enhanced: bool
    preset: str
    supports_seeking: bool


def create_unified_streaming_router(
    get_library_manager,
    get_multi_tier_buffer,
    chunked_processor_class,
    chunk_duration: float = 30.0
):
    """
    Factory function to create unified streaming router with dependencies.

    Args:
        get_library_manager: Callable that returns LibraryManager
        get_multi_tier_buffer: Callable that returns MultiTierBufferManager
        chunked_processor_class: ChunkedAudioProcessor class
        chunk_duration: Duration of each chunk in seconds
    """

    @router.get("/api/audio/stream/{track_id}/metadata")
    async def get_stream_metadata(
        track_id: int,
        enhanced: bool = Query(False),
        preset: str = Query("adaptive")
    ):
        """Get streaming metadata for player initialization."""
        try:
            library_manager = get_library_manager()
            track = library_manager.get_track(track_id)

            if not track:
                raise HTTPException(404, f"Track {track_id} not found")

            total_chunks = math.ceil(track.duration / chunk_duration)
            audio_format = "audio/wav" if enhanced else "audio/webm; codecs=opus"

            return StreamMetadata(
                track_id=track_id,
                duration=track.duration,
                total_chunks=total_chunks,
                chunk_duration=chunk_duration,
                format=audio_format,
                enhanced=enhanced,
                preset=preset,
                supports_seeking=True
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting metadata for track {track_id}: {e}")
            raise HTTPException(500, str(e))

    @router.get("/api/audio/stream/{track_id}/chunk/{chunk_idx}")
    async def get_audio_chunk(
        track_id: int,
        chunk_idx: int,
        enhanced: bool = Query(False),
        preset: str = Query("adaptive"),
        intensity: float = Query(1.0, ge=0.0, le=1.0)
    ):
        """
        Unified chunk endpoint - routes to MSE or MTB based on enhanced flag.

        This is the core intelligence that prevents dual playback conflicts.
        """
        try:
            start = time.time()

            if enhanced:
                # Enhanced path: Multi-tier buffer
                response = await _serve_enhanced_chunk(
                    track_id, chunk_idx, preset, intensity,
                    get_multi_tier_buffer, chunked_processor_class
                )
            else:
                # Unenhanced path: MSE with WebM
                response = await _serve_webm_chunk(
                    track_id, chunk_idx, get_library_manager, chunk_duration
                )

            elapsed = (time.time() - start) * 1000
            logger.info(
                f"Chunk delivered: track={track_id}, idx={chunk_idx}, "
                f"mode={'ENHANCED' if enhanced else 'MSE'}, latency={elapsed:.1f}ms"
            )

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error serving chunk: {e}")
            raise HTTPException(500, str(e))

    @router.get("/api/audio/stream/cache/stats")
    async def get_cache_stats():
        """Get cache statistics for monitoring."""
        try:
            encoder = get_encoder()
            webm_count, webm_size = encoder.get_cache_size()

            return {
                "webm_cache": {
                    "file_count": webm_count,
                    "size_mb": round(webm_size, 2)
                }
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            raise HTTPException(500, str(e))

    return router


async def _serve_enhanced_chunk(
    track_id, chunk_idx, preset, intensity,
    get_multi_tier_buffer, chunked_processor_class
):
    """Serve enhanced chunk via multi-tier buffer."""
    try:
        # For now, return a simple response
        # TODO: Integrate with actual multi-tier buffer
        logger.info(f"Enhanced chunk requested: {track_id}/{chunk_idx}")

        raise HTTPException(
            501,
            "Enhanced streaming not yet implemented - use existing player endpoint"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhanced chunk error: {e}")
        raise HTTPException(500, str(e))


async def _serve_webm_chunk(
    track_id, chunk_idx, get_library_manager, chunk_duration
):
    """Serve original audio as WebM for MSE."""
    try:
        from auralis.io.unified_loader import load_audio

        # Get track
        library_manager = get_library_manager()
        track = library_manager.get_track(track_id)

        if not track:
            raise HTTPException(404, f"Track {track_id} not found")

        # Check cache
        cache_key = f"track_{track_id}_webm_chunk_{chunk_idx}"
        encoder = get_encoder()
        cached_path = encoder.get_cached_path(cache_key)

        if cached_path and cached_path.exists():
            logger.info(f"WebM cache HIT: chunk {chunk_idx}")
            return StreamingResponse(
                open(cached_path, 'rb'),
                media_type="audio/webm; codecs=opus",
                headers={"X-Cache": "HIT"}
            )

        # Load and encode
        logger.info(f"WebM cache MISS: encoding chunk {chunk_idx}")

        start_time = chunk_idx * chunk_duration
        audio, sr = librosa.load(
            track.filepath,
            sr=None,
            mono=False,
            offset=start_time,
            duration=chunk_duration
        )

        # Librosa returns (channels, samples) for stereo, but sf.write needs (samples, channels)
        if audio.ndim == 2:
            audio = audio.T  # Transpose to (samples, channels)

        # Encode to WebM
        webm_path = await encode_audio_to_webm(audio, sr, cache_key)

        return StreamingResponse(
            open(webm_path, 'rb'),
            media_type="audio/webm; codecs=opus",
            headers={"X-Cache": "MISS"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebM chunk error: {e}")
        raise HTTPException(500, str(e))
