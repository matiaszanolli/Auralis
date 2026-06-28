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
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any
from collections.abc import Callable

# Import WAV encoder (replacing WebM for browser compatibility)
from encoding.wav_encoder import WAVEncoderError, encode_to_wav, read_wav_frame_info
from fastapi import APIRouter, HTTPException, Path as PathParam, Query, Response
from pydantic import BaseModel

from core.chunk_boundaries import CHUNK_DURATION, CHUNK_INTERVAL
from .dependencies import require_repository_factory

logger = logging.getLogger(__name__)
router = APIRouter(tags=["streaming"])

# ---------------------------------------------------------------------------
# Per-process audio file cache (fixes #2295, #3830)
# ---------------------------------------------------------------------------
# _get_original_wav_chunk() would otherwise reload the entire audio file for
# every chunk request — up to ~100 MB per call and O(concurrent_listeners)
# allocations. Decoded files are cached keyed by (filepath, mtime).
#
# This was @lru_cache(maxsize=8), but that bounds by ENTRY COUNT, not bytes:
# eight 24-bit/96 kHz albums (~150 MB each) pinned ~1.2 GB in heap with no
# eviction (#3830), and two concurrent streams of the same fresh file decoded
# it twice. The byte-bounded, locked cache below mirrors SimpleChunkCache's
# eviction discipline (core/audio_stream_controller.py) and collapses
# concurrent decodes of one file into a single in-flight load.
class _AudioFileCache:
    """Thread-safe, byte-bounded LRU cache of fully-decoded audio files."""

    def __init__(self, max_bytes: int = 512 * 1024 * 1024) -> None:
        self._cache: "OrderedDict[tuple[str, float], tuple[Any, int]]" = OrderedDict()
        self._max_bytes: int = max_bytes
        self._current_bytes: int = 0
        # Guards _cache, _current_bytes, and the _inflight registry.
        self._lock = threading.Lock()
        # Per-key decode locks so concurrent callers for the same fresh file
        # share one decode instead of racing (#3830).
        self._inflight: dict[tuple[str, float], threading.Lock] = {}

    def get_or_load(self, filepath: str, mtime: float) -> tuple[Any, int]:
        """Return the cached decode for (filepath, mtime), loading it once."""
        key = (filepath, mtime)

        with self._lock:
            hit = self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key)  # LRU touch
                return hit
            decode_lock = self._inflight.get(key)
            if decode_lock is None:
                decode_lock = threading.Lock()
                self._inflight[key] = decode_lock

        # Serialise the decode per key OUTSIDE the cache lock so other keys
        # proceed concurrently.
        with decode_lock:
            try:
                # Re-check: another thread may have populated the entry while
                # we waited for decode_lock.
                with self._lock:
                    hit = self._cache.get(key)
                    if hit is not None:
                        self._cache.move_to_end(key)
                        return hit

                from auralis.io.unified_loader import load_audio
                audio, sr = load_audio(filepath)
                audio.flags.writeable = False  # cached arrays are shared read-only

                with self._lock:
                    self._store(key, audio, sr)
                return audio, sr
            finally:
                # Drop the in-flight lock only if it's still ours (identity
                # guard) so a newer waiter's lock is never evicted.
                with self._lock:
                    if self._inflight.get(key) is decode_lock:
                        self._inflight.pop(key, None)

    def _store(self, key: tuple[str, float], audio: Any, sr: int) -> None:
        """Insert under self._lock, evicting oldest entries past the byte cap."""
        nbytes = int(getattr(audio, "nbytes", 0))
        if key in self._cache:
            old_audio, _ = self._cache.pop(key)
            self._current_bytes -= int(getattr(old_audio, "nbytes", 0))
        # Evict oldest until the newcomer fits; always keep the newcomer, even
        # if a single file exceeds the cap (matches SimpleChunkCache).
        while self._cache and self._current_bytes + nbytes > self._max_bytes:
            _old_key, (removed_audio, _) = self._cache.popitem(last=False)
            self._current_bytes -= int(getattr(removed_audio, "nbytes", 0))
        self._cache[key] = (audio, sr)
        self._current_bytes += nbytes

    def clear(self) -> None:
        """Drop all cached files (used on startup / by tests)."""
        with self._lock:
            self._cache.clear()
            self._current_bytes = 0


_audio_file_cache = _AudioFileCache()


def load_audio_with_invalidation(filepath: str) -> tuple[Any, int]:
    """Load decoded audio with file-change detection via mtime (#2590).

    Backed by a byte-bounded, thread-safe cache (#3830) so a large library
    can't pin unbounded RAM and concurrent streams of the same file decode once.
    """
    try:
        mtime = os.path.getmtime(filepath)
    except OSError:
        mtime = 0.0
    return _audio_file_cache.get_or_load(filepath, mtime)


def _compute_chunk_sample_layout(
    wav_bytes: bytes,
    chunk_idx: int,
    chunk_duration: int,
    chunk_interval: int,
) -> dict[str, int] | None:
    """Derive the per-chunk overlap layout from the actual WAV frame count.

    Makes each chunk response self-describing (#3872) so the frontend can trim
    overlap by exact sample count and place the chunk absolutely, instead of
    re-deriving from seconds-based metadata and trusting arrival order.

    The trailing overlap region is ``chunk_duration - chunk_interval`` seconds;
    a short final chunk (or a no-overlap config where duration == interval)
    carries no trailing overlap and is fully playable.

    Returns None on parse failure so streaming degrades gracefully (headers
    are simply omitted) rather than failing the request.
    """
    try:
        total_samples, sample_rate = read_wav_frame_info(wav_bytes)
    except WAVEncoderError as e:
        logger.warning(f"Could not derive chunk sample layout for chunk {chunk_idx}: {e}")
        return None

    overlap_samples = int(max(0, chunk_duration - chunk_interval) * sample_rate)
    # Only chunks longer than the interval portion carry trailing overlap.
    # Final/short chunks (and no-overlap configs) are fully playable.
    if total_samples <= int(chunk_interval * sample_rate):
        overlap_samples = 0
    playable_samples = max(0, total_samples - overlap_samples)
    start_sample_offset = int(chunk_idx * chunk_interval * sample_rate)

    return {
        "sample_rate": sample_rate,
        "total_samples": total_samples,
        "playable_samples": playable_samples,
        "overlap_samples": overlap_samples,
        "start_sample_offset": start_sample_offset,
    }


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


def create_wav_streaming_router(
    get_multi_tier_buffer: Callable[[], Any],
    chunked_audio_processor_class: Any,
    chunk_duration: int = int(CHUNK_DURATION),
    chunk_interval: int = int(CHUNK_INTERVAL),
    get_repository_factory: Callable[[], Any] | None = None
) -> APIRouter:
    """
    Factory function to create the unified WAV streaming router with dependencies.

    This is the new simplified architecture that replaces both MSE and MTB routers.

    Args:
        get_multi_tier_buffer: Callable that returns MultiTierBuffer instance
        chunked_audio_processor_class: ChunkedAudioProcessor class (now outputs WebM)
        chunk_duration: Duration of each chunk in seconds (default: chunk_boundaries.CHUNK_DURATION = 15)
        chunk_interval: Interval between chunk starts in seconds (default: chunk_boundaries.CHUNK_INTERVAL = 10, so 5s overlap)
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
            # Get track from library — wrap sync repo call so it doesn't block
            # the event loop (fixes #3495 / BE-NEW-37).
            track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)
            if not track:
                raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

            # Check if file exists — don't leak the full server path to the
            # client; the filename alone is enough for the user to recognise
            # the missing file (fixes #3541 / BE-NEW-83).
            file_exists = await asyncio.to_thread(os.path.exists, track.filepath)
            if not file_exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Audio file not found for track {track_id}",
                )

            # Calculate total chunks
            duration = track.duration if hasattr(track, 'duration') and track.duration else 0
            if duration == 0:
                # Use header-only get_audio_info (fast) rather than full
                # load_audio (multi-MB decode) when duration is missing
                # from the DB (fixes #3495 — was blocking event loop with
                # a full-file decode).
                try:
                    from auralis.io.unified_loader import get_audio_info
                    info_fallback = await asyncio.to_thread(get_audio_info, track.filepath)
                    duration = info_fallback.get('duration') or 180
                except Exception as e:
                    logger.error(f"Failed to read audio header for duration: {e}")
                    duration = 180  # Default to 3 minutes if header read fails

            # Calculate total chunks based on interval (not duration) for overlap model
            # With 15s chunks and 10s intervals: chunks start at 0s, 10s, 20s, etc.
            total_chunks = math.ceil(duration / chunk_interval)

            # Get actual sample rate from audio file without loading full audio
            try:
                from auralis.io.unified_loader import get_audio_info
                audio_info = await asyncio.to_thread(get_audio_info, track.filepath)
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
                overlap_duration=max(0, chunk_duration - chunk_interval)
            )

            logger.info(f"Stream metadata for track {track_id}: {total_chunks} chunks, {duration:.1f}s, "
                       f"chunk_duration={chunk_duration}s, chunk_interval={chunk_interval}s, WAV/PCM")
            return metadata

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get stream metadata: {e}")
            raise HTTPException(status_code=500, detail="Failed to get stream metadata")

    @router.get("/api/stream/{track_id}/chunk/{chunk_idx}")
    async def stream_chunk(
        track_id: int,
        chunk_idx: int = PathParam(..., ge=0, description="Chunk index (must be non-negative)"),
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
            # Self-describing overlap layout (#3872) — lets the frontend trim
            # overlap by exact sample count and place the chunk absolutely,
            # independent of arrival order or which cache tier served it:
            - X-Sample-Rate: Sample rate of the returned WAV
            - X-Total-Samples: Total sample frames in the WAV
            - X-Playable-Samples: Frames to play (total - trailing overlap)
            - X-Overlap-Samples: Trailing overlap frames to crossfade/trim
            - X-Start-Sample-Offset: Absolute track sample offset of this chunk

        Raises:
            HTTPException: If library not available, track not found, or processing fails
        """
        start_time = time.time()

        multi_tier_buffer = get_multi_tier_buffer()

        try:
            repos = get_repos()
            # Get track from library — wrap sync repo call so it doesn't block
            # the event loop (fixes #3495 / BE-NEW-37).
            track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)
            if not track:
                raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

            # Check if file exists — generic message; don't leak server path
            # (fixes #3541 / BE-NEW-83).
            file_exists = await asyncio.to_thread(os.path.exists, track.filepath)
            if not file_exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Audio file not found for track {track_id}",
                )

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

                    # Get the WAV chunk path (runs DSP pipeline — offload to
                    # thread). Bound it so a hung DSP call can't wedge the
                    # request forever (#3852, sibling of the per-chunk timeout
                    # in audio_stream_controller).
                    try:
                        chunk_path = await asyncio.wait_for(
                            asyncio.to_thread(processor.get_wav_chunk_path, chunk_idx),
                            timeout=30.0,
                        )
                    except TimeoutError:
                        logger.error(
                            f"Chunk {chunk_idx} DSP timed out for track {track_id} (30s)"
                        )
                        raise HTTPException(
                            status_code=500,
                            detail="Chunk processing timed out. File may be corrupt or on slow storage.",
                        )

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
                                audio_file = await asyncio.to_thread(mutagen.File, track.filepath)  # type: ignore[attr-defined]
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
                            detail="Chunk processing failed"
                        )

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Log performance
            logger.info(f"Chunk {chunk_idx} delivered: {cache_tier} cache, {latency_ms:.1f}ms latency, WAV/PCM")

            # Return audio chunk with metadata headers
            if wav_bytes is None:
                raise HTTPException(status_code=500, detail="Failed to generate audio chunk")

            headers = {
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

            # Make the chunk self-describing for overlap stitching (#3872):
            # derive exact sample counts from the WAV frame count so the
            # frontend trims overlap precisely and can place the chunk
            # absolutely regardless of arrival order or cache tier.
            layout = _compute_chunk_sample_layout(
                wav_bytes, chunk_idx, chunk_duration, chunk_interval
            )
            if layout is not None:
                headers["X-Sample-Rate"] = str(layout["sample_rate"])
                headers["X-Total-Samples"] = str(layout["total_samples"])
                headers["X-Playable-Samples"] = str(layout["playable_samples"])
                headers["X-Overlap-Samples"] = str(layout["overlap_samples"])
                headers["X-Start-Sample-Offset"] = str(layout["start_sample_offset"])

            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers=headers,
            )

        except HTTPException:
            raise
        except Exception as e:
            import traceback
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Chunk streaming failed after {latency_ms:.1f}ms: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail="Chunk streaming failed")

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
        # Load audio from the process-level LRU cache — avoids reloading the
        # entire file (~100 MB) for every chunk request (fixes #2295).
        audio, sr = await asyncio.to_thread(load_audio_with_invalidation, filepath)

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
                detail="WAV encoding failed"
            )

    return router
