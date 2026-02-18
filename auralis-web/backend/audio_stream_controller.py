#!/usr/bin/env python3

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

import asyncio
import hashlib
import json
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any
from collections.abc import Callable

import numpy as np
from cache.manager import StreamlinedCacheManager
from chunked_processor import ChunkedAudioProcessor, apply_crossfade_between_chunks
from fastapi import WebSocket
from fingerprint_generator import FingerprintGenerator

from auralis.library.repositories.factory import RepositoryFactory

logger = logging.getLogger(__name__)

# Maximum number of encoded frames queued ahead of the WebSocket sender.
# Limits Python-heap memory when the client is slower than the encoder.
_SEND_QUEUE_MAXSIZE: int = 4

# Maximum number of concurrent audio streams (enhanced, normal, seek).
# Each stream holds a ChunkedProcessor in memory; unbounded concurrency
# causes OOM under load (issue #2185).
MAX_CONCURRENT_STREAMS: int = 10


class SimpleChunkCache:
    """Simple in-memory cache for processed audio chunks."""

    # Cache version - increment when chunk processing logic changes
    # This invalidates all cached chunks when we fix bugs in extraction/processing
    CACHE_VERSION = 3  # v3: Added _extract_chunk_segment to process_chunk for proper overlap handling

    def __init__(self, max_chunks: int = 50) -> None:
        """
        Initialize chunk cache.

        Args:
            max_chunks: Maximum number of chunks to keep in memory
        """
        self.cache: OrderedDict[str, tuple[np.ndarray, int]] = OrderedDict()
        self.max_chunks: int = max_chunks

    def _make_key(self, track_id: int, chunk_idx: int, preset: str, intensity: float) -> str:
        """Generate cache key from parameters."""
        # Include CACHE_VERSION to invalidate stale cached chunks when processing logic changes
        key_str = f"v{self.CACHE_VERSION}:{track_id}:{chunk_idx}:{preset}:{intensity:.2f}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(
        self,
        track_id: int,
        chunk_idx: int,
        preset: str,
        intensity: float
    ) -> tuple[np.ndarray, int] | None:
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

    def invalidate_chunk(self, track_id: int, chunk_idx: int, preset: str, intensity: float) -> None:
        """Remove a specific chunk from cache after a processing failure.

        Prevents a stale/corrupt cache entry from causing repeated failures on retry.

        Args:
            track_id: Track ID the chunk belongs to
            chunk_idx: Index of the failed chunk
            preset: Processing preset used
            intensity: Processing intensity used
        """
        key = self._make_key(track_id, chunk_idx, preset, intensity)
        if self.cache.pop(key, None) is not None:
            logger.debug(f"Invalidated stale cache entry: chunk {chunk_idx} of track {track_id}")


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
        chunked_processor_class: type[ChunkedAudioProcessor] | None = None,
        get_repository_factory: Callable[[], RepositoryFactory] | None = None,
        cache_manager: StreamlinedCacheManager | SimpleChunkCache | None = None
    ) -> None:
        """
        Initialize AudioStreamController.

        Args:
            chunked_processor_class: ChunkedAudioProcessor class for processing
            get_repository_factory: Callable that returns RepositoryFactory for track lookup
            cache_manager: Optional cache manager for chunk caching.
        """
        self.chunked_processor_class: type[ChunkedAudioProcessor] | None = chunked_processor_class
        self._get_repository_factory: Callable[[], RepositoryFactory] | None = get_repository_factory

        # Use provided cache manager or fallback to SimpleChunkCache
        self.cache_manager: StreamlinedCacheManager | SimpleChunkCache = cache_manager or SimpleChunkCache()
        self._stream_type: str | None = None  # Set by public streaming methods ("enhanced" or "normal")
        logger.info(f"AudioStreamController initialized with cache manager: {type(self.cache_manager).__name__}")

        # NEW (Phase 7.3): Fingerprint generator for on-demand generation
        self.fingerprint_generator: FingerprintGenerator | None = None
        if self._get_repository_factory:
            try:
                # Get session factory from the first repository factory call
                factory = self._get_repository_factory()
                if hasattr(factory, 'session_factory'):
                    self.fingerprint_generator = FingerprintGenerator(
                        session_factory=factory.session_factory,
                        get_repository_factory=self._get_repository_factory
                    )
                    logger.info("✅ FingerprintGenerator initialized for on-demand fingerprint generation")
                else:
                    logger.warning("RepositoryFactory missing session_factory attribute, fingerprint generation unavailable")
            except Exception as e:
                logger.warning(f"Failed to initialize FingerprintGenerator: {e}, proceeding without on-demand fingerprint generation")

        self.active_streams: dict[int, Any] = {}  # track_id -> streaming task
        # Semaphore that caps concurrent streams (issue #2185)
        self._stream_semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)

        # Store previous chunk tails for crossfading (track_id -> tail samples)
        self._chunk_tails: dict[int, np.ndarray] = {}

    def _is_websocket_connected(self, websocket: WebSocket) -> bool:
        """
        Check if WebSocket is still connected and can receive messages.

        Returns:
            True if WebSocket is connected, False if disconnected or closing.
        """
        try:
            return websocket.client_state.name == "CONNECTED"
        except Exception:
            return False

    async def _safe_send(self, websocket: WebSocket, message: dict[str, Any]) -> bool:
        """
        Safely send a message to WebSocket, handling disconnection gracefully.

        Args:
            websocket: WebSocket connection
            message: Message dict to send as JSON

        Returns:
            True if message was sent, False if WebSocket was disconnected.
        """
        if not self._is_websocket_connected(websocket):
            logger.debug("WebSocket disconnected, skipping send")
            return False
        try:
            await websocket.send_text(json.dumps(message))
            return True
        except RuntimeError as e:
            if "close message" in str(e).lower():
                logger.debug(f"WebSocket closed during send: {e}")
            else:
                logger.warning(f"WebSocket send failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error sending WebSocket message: {e}")
            return False

    async def _ensure_fingerprint_available(
        self,
        track_id: int,
        filepath: str,
        websocket: WebSocket | None = None
    ) -> bool:
        """
        Ensure fingerprint is available (cached or generated).

        Attempts to load or generate a fingerprint before streaming begins.
        If generation fails, proceeds gracefully without fingerprint.

        Sends progress messages to WebSocket if provided.

        Args:
            track_id: ID of the track
            filepath: Path to audio file
            websocket: Optional WebSocket connection for progress messages

        Returns:
            True if fingerprint was available/generated, False if not available
        """
        if not self.fingerprint_generator:
            logger.debug(f"FingerprintGenerator not available, skipping fingerprint loading")
            return False

        try:
            logger.info(f"📊 Ensuring fingerprint available for track {track_id}...")

            # Send fingerprint_progress: analyzing message
            if websocket:
                await self._send_fingerprint_progress(
                    websocket,
                    track_id=track_id,
                    status="analyzing",
                    message="Analyzing audio for optimal mastering..."
                )

            fingerprint_data = await self.fingerprint_generator.get_or_generate(
                track_id=track_id,
                filepath=filepath
            )

            if fingerprint_data:
                logger.info(f"✅ Fingerprint is now available for track {track_id} (ready for adaptive mastering)")

                # Send fingerprint_progress: complete message
                if websocket:
                    await self._send_fingerprint_progress(
                        websocket,
                        track_id=track_id,
                        status="complete",
                        message="Fingerprint analysis complete"
                    )

                return True
            else:
                logger.warning(f"⚠️  Fingerprint unavailable for track {track_id}, proceeding without optimization")

                # Send fingerprint_progress: failed message
                if websocket:
                    await self._send_fingerprint_progress(
                        websocket,
                        track_id=track_id,
                        status="failed",
                        message="Fingerprint generation failed, using default mastering"
                    )

                return False

        except Exception as e:
            logger.warning(f"Fingerprint preparation failed for track {track_id}: {e}, proceeding without optimization")

            # Send fingerprint_progress: error message
            if websocket:
                await self._send_fingerprint_progress(
                    websocket,
                    track_id=track_id,
                    status="error",
                    message=f"Fingerprint error: {str(e)}"
                )

            return False

    async def _check_or_queue_fingerprint(
        self,
        track_id: int,
        filepath: str,
        websocket: WebSocket | None = None
    ) -> bool:
        """
        Non-blocking fingerprint check - queue generation instead of waiting.

        Phase 7.5: Don't block streaming on fingerprint generation.
        - If fingerprint exists in database: return True immediately
        - If fingerprint missing: queue for background generation, return False
        - Stream starts immediately with standard mastering either way

        Args:
            track_id: ID of the track
            filepath: Path to audio file
            websocket: Optional WebSocket connection for progress messages

        Returns:
            True if fingerprint is cached and ready, False if not (generation queued)
        """
        if not self._get_repository_factory:
            logger.debug(f"RepositoryFactory not available, skipping fingerprint check")
            return False

        try:
            # Quick database check - O(1) lookup, no blocking
            factory = self._get_repository_factory()
            fingerprint_repo = factory.fingerprints

            if fingerprint_repo.exists(track_id):
                # Fingerprint already cached - streaming will use optimized mastering
                logger.info(f"✅ Fingerprint cached for track {track_id} (instant lookup)")
                if websocket:
                    await self._send_fingerprint_progress(
                        websocket,
                        track_id=track_id,
                        status="cached",
                        message="Using cached audio analysis"
                    )
                return True

            # Fingerprint not cached - queue for background generation
            logger.info(f"📋 Fingerprint not cached for track {track_id}, queuing for background generation")

            # Try to enqueue via fingerprint queue (non-blocking)
            try:
                from fingerprint_queue import get_fingerprint_queue
                queue = get_fingerprint_queue()
                if queue:
                    added = queue.enqueue(track_id)
                    if added:
                        logger.info(f"📋 Track {track_id} queued for background fingerprinting")
                    else:
                        logger.debug(f"Track {track_id} already queued or processing")
                else:
                    logger.debug(f"Fingerprint queue not available")
            except Exception as q_err:
                logger.debug(f"Could not enqueue track {track_id}: {q_err}")

            # Send progress message - using standard mastering
            if websocket:
                await self._send_fingerprint_progress(
                    websocket,
                    track_id=track_id,
                    status="queued",
                    message="Audio analysis queued, using standard mastering"
                )

            return False

        except Exception as e:
            logger.debug(f"Fingerprint check failed for track {track_id}: {e}")
            return False

    async def stream_enhanced_audio(
        self,
        track_id: int,
        preset: str,
        intensity: float,
        websocket: WebSocket,
        on_progress: Callable[[int, float, str], Any] | None = None
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
        self._stream_type = "enhanced"

        if not self.chunked_processor_class:
            raise ValueError("ChunkedProcessor not available")

        if not self._get_repository_factory:
            raise ValueError("RepositoryFactory not available")

        # Limit concurrent streams to prevent unbounded memory growth (#2185)
        try:
            await asyncio.wait_for(self._stream_semaphore.acquire(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(
                f"Stream limit ({MAX_CONCURRENT_STREAMS}) reached, rejecting track {track_id}"
            )
            await self._send_error(websocket, track_id, "Server busy - too many active streams")
            return

        # Get track from library
        try:
            factory = self._get_repository_factory()
            track = factory.tracks.get_by_id(track_id)
            if not track:
                await self._send_error(websocket, track_id, "Track not found")
                self._stream_semaphore.release()
                return

            if not Path(track.filepath).exists():
                await self._send_error(
                    websocket, track_id, f"Audio file not found: {track.filepath}"
                )
                self._stream_semaphore.release()
                return
        except Exception as e:
            logger.error(f"Failed to load track {track_id}: {e}")
            await self._send_error(websocket, track_id, str(e))
            self._stream_semaphore.release()
            return

        try:
            # Create processor for this track with timeout (#2125)
            try:
                processor: ChunkedAudioProcessor = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.chunked_processor_class,
                        track_id=track_id,
                        filepath=str(track.filepath),
                        preset=preset,
                        intensity=intensity,
                    ),
                    timeout=30.0
                )
            except TimeoutError:
                error_msg = "Audio processor initialization timed out. File may be corrupt or on slow storage."
                logger.error(f"Processor instantiation timed out for track {track_id} (30s)")
                await self._send_error(websocket, track_id, error_msg)
                return

            # Ensure processor has loaded metadata
            assert processor.total_chunks is not None
            assert processor.sample_rate is not None
            assert processor.channels is not None
            assert processor.duration is not None

            # Phase 7.5: Non-blocking fingerprint check
            # Check if fingerprint exists in cache - if not, queue for background generation
            # Don't wait for generation - start streaming immediately with standard mastering
            fingerprint_available = await self._check_or_queue_fingerprint(
                track_id=track_id,
                filepath=str(track.filepath),
                websocket=websocket
            )
            if fingerprint_available:
                logger.info(f"🎯 Adaptive mastering will use fingerprint-optimized parameters (cached)")
            else:
                logger.info(f"📊 Streaming with standard adaptive mastering (fingerprint queued for background generation)")

            logger.info(
                f"Starting audio stream: track={track_id}, preset={preset}, "
                f"intensity={intensity}, chunks={processor.total_chunks}"
            )

            # Send stream start message with metadata
            if not await self._send_stream_start(
                websocket,
                track_id=track_id,
                preset=preset,
                intensity=intensity,
                sample_rate=processor.sample_rate,
                channels=processor.channels,
                total_chunks=processor.total_chunks,
                chunk_duration=processor.chunk_duration,
                total_duration=processor.duration,
            ):
                logger.info(f"WebSocket disconnected, cannot start stream")
                return

            # Process and stream chunks
            for chunk_idx in range(processor.total_chunks):
                if not self._is_websocket_connected(websocket):
                    logger.info(f"WebSocket disconnected, stopping stream")
                    break

                try:
                    # Process chunk with fast-start for first chunk
                    await self._process_and_stream_chunk(
                        chunk_idx, processor, websocket, on_progress
                    )

                    # Progress update
                    if on_progress:
                        # total_chunks is guaranteed non-None due to assertion above
                        progress = ((chunk_idx + 1) / processor.total_chunks) * 100
                        await on_progress(track_id, progress, f"Processed chunk {chunk_idx + 1}")

                except Exception as chunk_error:
                    logger.error(
                        f"Failed to process chunk {chunk_idx}: {chunk_error}",
                        exc_info=True
                    )
                    # Compute recovery position: start of the failed chunk (issue #2085)
                    recovery_position: float = chunk_idx * processor.chunk_duration
                    # Evict any stale cache entry for the failed chunk so a retry
                    # processes it fresh rather than replaying corrupt data (issue #2085)
                    if isinstance(self.cache_manager, SimpleChunkCache):
                        self.cache_manager.invalidate_chunk(
                            track_id=track_id,
                            chunk_idx=chunk_idx,
                            preset=preset,
                            intensity=intensity,
                        )
                    # Proactively remove crossfade tail; the outer finally also does
                    # this, but being explicit ensures it happens before the error
                    # message is sent (issue #2085)
                    self._chunk_tails.pop(track_id, None)
                    await self._send_error(
                        websocket,
                        track_id,
                        f"Failed to process chunk {chunk_idx}: {chunk_error}",
                        recovery_position=recovery_position,
                    )
                    return

            # Stream complete
            logger.info(f"Audio stream complete: track={track_id}")
            # Both are guaranteed non-None due to assertions above
            await self._send_stream_end(
                websocket,
                track_id=track_id,
                total_samples=int(processor.duration * processor.sample_rate),
                duration=processor.duration,
            )

        except Exception as e:
            # Only log at error level if it's not a normal disconnection
            if "close message" in str(e).lower():
                logger.info(f"Audio streaming stopped: client disconnected")
            else:
                logger.error(f"Audio streaming failed: {e}", exc_info=True)
                # Only try to send error if WebSocket is still connected
                if self._is_websocket_connected(websocket):
                    await self._send_error(websocket, track_id, str(e))
        finally:
            # Clean up chunk tail storage for this track
            self._chunk_tails.pop(track_id, None)
            self._stream_semaphore.release()

    async def stream_normal_audio(
        self,
        track_id: int,
        websocket: WebSocket,
        on_progress: Callable[[int, float, str], Any] | None = None
    ) -> None:
        """
        Stream original (unprocessed) audio chunks to client via WebSocket.

        Used for comparing original vs enhanced audio. Same chunking format as enhanced,
        but with no DSP processing applied.

        Args:
            track_id: Track ID to stream
            websocket: WebSocket connection to client
            on_progress: Optional callback for progress updates

        Raises:
            ValueError: If track not found or file unavailable
            Exception: If loading or streaming fails
        """
        self._stream_type = "normal"

        import soundfile as sf

        if not self._get_repository_factory:
            raise ValueError("RepositoryFactory not available")

        # Limit concurrent streams to prevent unbounded memory growth (#2185)
        try:
            await asyncio.wait_for(self._stream_semaphore.acquire(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(
                f"Stream limit ({MAX_CONCURRENT_STREAMS}) reached, rejecting track {track_id}"
            )
            await self._send_error(websocket, track_id, "Server busy - too many active streams")
            return

        # Get track from library
        try:
            factory = self._get_repository_factory()
            track = factory.tracks.get_by_id(track_id)
            if not track:
                await self._send_error(websocket, track_id, "Track not found")
                self._stream_semaphore.release()
                return

            if not Path(track.filepath).exists():
                await self._send_error(
                    websocket, track_id, f"Audio file not found: {track.filepath}"
                )
                self._stream_semaphore.release()
                return
        except Exception as e:
            logger.error(f"Failed to load track {track_id}: {e}")
            await self._send_error(websocket, track_id, str(e))
            self._stream_semaphore.release()
            return

        try:
            # Read file metadata only — do NOT load audio data yet (#2121).
            # sf.read() would allocate ~200 MB for a 10-min stereo track; instead
            # we open the SoundFile, record its shape, and close it immediately.
            def _get_audio_info(filepath: str) -> tuple[int, int, int]:
                with sf.SoundFile(filepath) as audio_file:
                    return audio_file.samplerate, audio_file.channels, len(audio_file)

            sample_rate, channels, total_frames = await asyncio.to_thread(
                _get_audio_info, str(track.filepath)
            )

            duration = total_frames / sample_rate

            # Calculate chunks (NO overlap for normal streaming - no crossfade applied)
            chunk_duration = 15.0  # Chunk duration in seconds
            chunk_samples = int(chunk_duration * sample_rate)

            # For normal path: chunk_interval = chunk_duration (no overlap)
            # Unlike enhanced path which uses ChunkedProcessor with server-side crossfade,
            # normal path sends chunks without processing, so overlap would cause duplication
            interval_samples = chunk_samples  # No overlap

            total_chunks = max(1, int(np.ceil(total_frames / interval_samples)))

            logger.info(
                f"Starting normal audio stream: track={track_id}, "
                f"duration={duration:.1f}s, chunks={total_chunks}, sr={sample_rate}Hz"
            )

            # Send stream start message
            if not await self._send_stream_start(
                websocket,
                track_id=track_id,
                preset="none",  # No processing
                intensity=1.0,   # Full intensity (original)
                sample_rate=sample_rate,
                channels=channels,
                total_chunks=total_chunks,
                chunk_duration=chunk_duration,
                total_duration=duration,
            ):
                logger.info(f"WebSocket disconnected, cannot start stream")
                return

            # Helper: open → seek → read → close for a single chunk (#2121).
            # Peak memory per stream is now one chunk (~13 MB for 15 s stereo 44.1 kHz)
            # instead of the full file (~200 MB for 10 min).
            def _read_audio_chunk(filepath: str, start: int, frames: int) -> np.ndarray:
                with sf.SoundFile(filepath) as audio_file:
                    audio_file.seek(start)
                    # always_2d=True: mono returned as (N, 1) matching stereo shape
                    # fill_value=0.0: pads last chunk automatically when fewer frames remain
                    return audio_file.read(
                        frames=frames, dtype='float32', always_2d=True, fill_value=0.0
                    )

            # Stream chunks one at a time without processing
            for chunk_idx in range(total_chunks):
                if not self._is_websocket_connected(websocket):
                    logger.info(f"WebSocket disconnected, stopping stream")
                    break

                try:
                    start_sample = chunk_idx * interval_samples
                    chunk_audio: np.ndarray = await asyncio.to_thread(
                        _read_audio_chunk, str(track.filepath), start_sample, chunk_samples
                    )

                    # Stream the chunk
                    await self._send_pcm_chunk(
                        websocket,
                        pcm_samples=chunk_audio,
                        chunk_index=chunk_idx,
                        total_chunks=total_chunks,
                        crossfade_samples=0,  # No overlap in normal path (no crossfade applied)
                    )

                    # Progress update
                    if on_progress:
                        progress = ((chunk_idx + 1) / total_chunks) * 100
                        await on_progress(track_id, progress, f"Streamed chunk {chunk_idx + 1}")

                except Exception as chunk_error:
                    logger.error(f"Failed to stream chunk {chunk_idx}: {chunk_error}", exc_info=True)
                    # Recovery position: start of the failed chunk (issue #2085)
                    normal_recovery_position: float = chunk_idx * chunk_duration
                    await self._send_error(
                        websocket,
                        track_id,
                        f"Failed to stream chunk {chunk_idx}: {chunk_error}",
                        recovery_position=normal_recovery_position,
                    )
                    return

            # Stream complete
            logger.info(f"Normal audio stream complete: track={track_id}")
            await self._send_stream_end(
                websocket,
                track_id=track_id,
                total_samples=total_frames,
                duration=duration,
            )

        except Exception as e:
            # Only log at error level if it's not a normal disconnection
            if "close message" in str(e).lower():
                logger.info(f"Normal audio streaming stopped: client disconnected")
            else:
                logger.error(f"Normal audio streaming failed: {e}", exc_info=True)
                # Only try to send error if WebSocket is still connected
                if self._is_websocket_connected(websocket):
                    await self._send_error(websocket, track_id, str(e))
        finally:
            self._stream_semaphore.release()

    async def _process_and_stream_chunk(
        self,
        chunk_index: int,
        processor: ChunkedAudioProcessor,
        websocket: WebSocket,
        on_progress: Callable[[int, float, str], Any] | None = None,
    ) -> None:
        """
        Process single chunk and stream PCM samples to client.

        Implements caching to avoid reprocessing chunks with same parameters.
        Applies server-side crossfade to smooth chunk boundaries.

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
        pcm_samples: np.ndarray | None = None
        sr: int | None = None
        cache_hit: bool = False

        try:
            # Handle union type: both cache managers have get() method
            if isinstance(self.cache_manager, SimpleChunkCache):
                cached_result: tuple[np.ndarray, int] | None = self.cache_manager.get(
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
            # Process chunk - returns both path (for durability) and audio array (for streaming)
            # This avoids the disk round-trip of saving then immediately reading back
            try:
                chunk_path, pcm_samples = await processor.process_chunk_safe(chunk_index, fast_start=fast_start)
                sr = processor.sample_rate

                logger.debug(
                    f"Chunk {chunk_index}: processed {len(pcm_samples)} samples at {sr}Hz "
                    f"(skipped disk read, used array directly)"
                )

                # Store in cache for future use
                try:
                    if isinstance(self.cache_manager, SimpleChunkCache) and sr is not None:
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
                logger.error(f"Failed to process chunk {chunk_index}: {e}")
                raise

        # Stream PCM samples to client
        try:
            # pcm_samples should never be None at this point (either from cache or loaded from disk)
            assert pcm_samples is not None, "PCM samples must be loaded before streaming"
            assert sr is not None, "Sample rate must be set before streaming"
            assert processor.total_chunks is not None, "total_chunks must be set"
            assert processor.sample_rate is not None, "sample_rate must be set"

            # Apply server-side crossfade to smooth chunk boundaries
            # Use short crossfade (200ms) to prevent clicks without creating artifacts
            crossfade_duration_ms = 200  # milliseconds
            crossfade_samples = int(crossfade_duration_ms * processor.sample_rate / 1000)

            # Apply crossfade if not the first chunk
            if chunk_index > 0 and processor.track_id in self._chunk_tails:
                prev_tail = self._chunk_tails[processor.track_id]
                pcm_samples = self._apply_boundary_crossfade(
                    prev_tail, pcm_samples, crossfade_samples
                )
                logger.debug(
                    f"Applied {crossfade_duration_ms}ms crossfade between chunks "
                    f"{chunk_index-1} and {chunk_index}"
                )

            # Store tail for next chunk (last N samples) if not the last chunk
            if chunk_index < processor.total_chunks - 1:
                tail_samples = min(crossfade_samples, len(pcm_samples))
                self._chunk_tails[processor.track_id] = pcm_samples[-tail_samples:].copy()
            else:
                # Last chunk - clean up tail storage
                self._chunk_tails.pop(processor.track_id, None)

            await self._send_pcm_chunk(
                websocket,
                pcm_samples=pcm_samples,
                chunk_index=chunk_index,
                total_chunks=processor.total_chunks,
                crossfade_samples=crossfade_samples,
            )
        except Exception as e:
            logger.error(f"Failed to stream chunk {chunk_index}: {e}")
            raise

    def _apply_boundary_crossfade(
        self, prev_tail: np.ndarray, current_chunk: np.ndarray, crossfade_samples: int
    ) -> np.ndarray:
        """
        Apply crossfade at chunk boundary to prevent clicks.

        Takes the tail of the previous chunk and the head of the current chunk,
        applies equal-power crossfade, and returns the current chunk with
        crossfaded beginning.

        Args:
            prev_tail: Last N samples from previous chunk
            current_chunk: Current chunk audio
            crossfade_samples: Number of samples to crossfade

        Returns:
            Current chunk with crossfaded beginning
        """
        # Ensure we don't crossfade more than available
        actual_crossfade = min(crossfade_samples, len(prev_tail), len(current_chunk))

        if actual_crossfade <= 0:
            return current_chunk

        # Get crossfade regions
        tail_region = prev_tail[-actual_crossfade:]
        head_region = current_chunk[:actual_crossfade]

        # Create equal-power fade curves (smoother than linear)
        fade_out = np.cos(np.linspace(0, np.pi / 2, actual_crossfade)) ** 2
        fade_in = np.sin(np.linspace(0, np.pi / 2, actual_crossfade)) ** 2

        # Handle stereo
        if tail_region.ndim == 2:
            fade_out = fade_out[:, np.newaxis]
            fade_in = fade_in[:, np.newaxis]

        # Apply crossfade
        crossfaded = tail_region * fade_out + head_region * fade_in

        # Replace beginning of current chunk with crossfaded region
        result = current_chunk.copy()
        result[:actual_crossfade] = crossfaded

        return result

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

        # Bounded producer/consumer: limits Python-heap accumulation when the
        # client is slower than the encoder (backpressure for issue #2122).
        # The producer encodes one frame at a time and blocks at queue.put()
        # once _SEND_QUEUE_MAXSIZE frames are queued.  The consumer sends via
        # _safe_send() which handles disconnects; on disconnect it signals the
        # producer to stop so we don't keep encoding into a dead stream.
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(
            maxsize=_SEND_QUEUE_MAXSIZE
        )
        abort_event: asyncio.Event = asyncio.Event()

        async def _producer() -> None:
            try:
                for frame_idx in range(num_frames):
                    if abort_event.is_set():
                        break
                    start_idx: int = frame_idx * samples_per_frame
                    end_idx: int = min(start_idx + samples_per_frame, total_samples)
                    frame_samples: np.ndarray = pcm_samples[start_idx:end_idx]

                    pcm_bytes: bytes = frame_samples.tobytes()
                    pcm_base64: str = base64.b64encode(pcm_bytes).decode("ascii")

                    message: dict[str, Any] = {
                        "type": "audio_chunk",
                        "data": {
                            "chunk_index": chunk_index,
                            "chunk_count": total_chunks,
                            "frame_index": frame_idx,
                            "frame_count": num_frames,
                            "samples": pcm_base64,
                            "sample_count": frame_samples.size,
                            # Crossfade is applied server-side in _process_and_stream_chunk
                            # to prevent audible clicks at chunk boundaries.
                            # Frontend receives pre-crossfaded audio, so no client-side crossfade needed.
                            "crossfade_samples": crossfade_samples,  # For monitoring/debugging
                            "stream_type": self._stream_type,
                        },
                    }
                    await queue.put(message)
            finally:
                await queue.put(None)  # sentinel — always sent so consumer can exit

        async def _consumer() -> None:
            while True:
                message = await queue.get()
                if message is None:
                    break
                sent: bool = await self._safe_send(websocket, message)
                if not sent:
                    # Client disconnected — stop the producer and drain the queue
                    abort_event.set()
                    while not queue.empty():
                        queue.get_nowait()
                    break
                frame_idx = message["data"]["frame_index"]
                logger.debug(
                    f"Streamed chunk {chunk_index} frame {frame_idx}/{num_frames}: "
                    f"{message['data']['sample_count']} samples"
                )

        await asyncio.gather(_producer(), _consumer())

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
    ) -> bool:
        """Send audio_stream_start message to client.

        Returns:
            True if message was sent, False if WebSocket was disconnected.
        """
        message: dict[str, Any] = {
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
                "stream_type": self._stream_type,
            },
        }
        if await self._safe_send(websocket, message):
            logger.debug(f"Sent stream_start: {total_chunks} chunks, {total_duration}s duration")
            return True
        return False

    async def _send_stream_end(
        self,
        websocket: WebSocket,
        track_id: int,
        total_samples: int,
        duration: float,
    ) -> bool:
        """Send audio_stream_end message to client.

        Returns:
            True if message was sent, False if WebSocket was disconnected.
        """
        message: dict[str, Any] = {
            "type": "audio_stream_end",
            "data": {
                "track_id": track_id,
                "total_samples": total_samples,
                "duration": duration,
                "stream_type": self._stream_type,
            },
        }
        if await self._safe_send(websocket, message):
            logger.debug(f"Sent stream_end: {total_samples} samples, {duration}s duration")
            return True
        return False

    async def _send_error(
        self,
        websocket: WebSocket,
        track_id: int,
        error_message: str,
        recovery_position: float | None = None,
    ) -> None:
        """Send audio_stream_error message to client.

        Args:
            websocket: WebSocket connection to send the error to
            track_id: ID of the track that failed
            error_message: Human-readable error description
            recovery_position: Seconds into the track from which the client may
                seek/retry (set when a specific chunk fails, issue #2085).
        """
        data: dict[str, Any] = {
            "track_id": track_id,
            "error": error_message,
            "code": "STREAMING_ERROR",
            "stream_type": self._stream_type,
        }
        if recovery_position is not None:
            data["recovery_position"] = recovery_position
        message: dict[str, Any] = {"type": "audio_stream_error", "data": data}
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    async def _send_fingerprint_progress(
        self,
        websocket: WebSocket,
        track_id: int,
        status: str,
        message: str
    ) -> None:
        """
        Send fingerprint_progress message to client.

        Args:
            websocket: WebSocket connection
            track_id: Track ID being analyzed
            status: Progress status (analyzing, complete, failed, error)
            message: Human-readable progress message
        """
        progress_message: dict[str, Any] = {
            "type": "fingerprint_progress",
            "data": {
                "track_id": track_id,
                "status": status,
                "message": message,
                "stream_type": self._stream_type,
            },
        }
        try:
            await websocket.send_text(json.dumps(progress_message))
            logger.debug(f"Sent fingerprint_progress: track={track_id}, status={status}")
        except Exception as e:
            logger.error(f"Failed to send fingerprint_progress message: {e}")

    async def stream_enhanced_audio_from_position(
        self,
        track_id: int,
        preset: str,
        intensity: float,
        websocket: WebSocket,
        start_position: float,
        on_progress: Callable[[int, float, str], Any] | None = None
    ) -> None:
        """
        Stream enhanced audio chunks starting from a specific position (seek).

        This method is used for seeking - it starts streaming from the chunk
        containing the target position, with an offset applied for precise seeking.

        Args:
            track_id: Track ID to process and stream
            preset: Processing preset (adaptive, gentle, warm, etc.)
            intensity: Processing intensity (0.0-1.0)
            websocket: WebSocket connection to client
            start_position: Position in seconds to start streaming from
            on_progress: Optional callback for progress updates

        Raises:
            ValueError: If track not found or processor unavailable
            Exception: If processing or streaming fails
        """
        self._stream_type = "enhanced"

        if not self.chunked_processor_class:
            raise ValueError("ChunkedProcessor not available")

        if not self._get_repository_factory:
            raise ValueError("RepositoryFactory not available")

        # Limit concurrent streams to prevent unbounded memory growth (#2185)
        try:
            await asyncio.wait_for(self._stream_semaphore.acquire(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(
                f"Stream limit ({MAX_CONCURRENT_STREAMS}) reached, rejecting track {track_id}"
            )
            await self._send_error(websocket, track_id, "Server busy - too many active streams")
            return

        # Get track from library
        try:
            factory = self._get_repository_factory()
            track = factory.tracks.get_by_id(track_id)
            if not track:
                await self._send_error(websocket, track_id, "Track not found")
                self._stream_semaphore.release()
                return

            if not Path(track.filepath).exists():
                await self._send_error(
                    websocket, track_id, f"Audio file not found: {track.filepath}"
                )
                self._stream_semaphore.release()
                return
        except Exception as e:
            logger.error(f"Failed to load track {track_id}: {e}")
            await self._send_error(websocket, track_id, str(e))
            self._stream_semaphore.release()
            return

        try:
            # Create processor for this track with timeout (#2125)
            try:
                processor: ChunkedAudioProcessor = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.chunked_processor_class,
                        track_id=track_id,
                        filepath=str(track.filepath),
                        preset=preset,
                        intensity=intensity,
                    ),
                    timeout=30.0
                )
            except TimeoutError:
                error_msg = "Audio processor initialization timed out during seek. File may be corrupt or on slow storage."
                logger.error(f"Processor instantiation timed out for track {track_id} during seek (30s)")
                await self._send_error(websocket, track_id, error_msg)
                return

            # Ensure processor has loaded metadata
            assert processor.total_chunks is not None
            assert processor.sample_rate is not None
            assert processor.channels is not None
            assert processor.duration is not None

            # Calculate which chunk to start from based on position
            # Chunks overlap, so we need to find the chunk that contains this position
            chunk_interval = getattr(processor, 'chunk_interval', 10.0)  # Default 10s interval
            start_chunk_idx = int(start_position / chunk_interval)
            start_chunk_idx = max(0, min(start_chunk_idx, processor.total_chunks - 1))

            # Calculate the offset within the chunk (for precise seeking)
            chunk_start_time = start_chunk_idx * chunk_interval
            seek_offset = start_position - chunk_start_time

            logger.info(
                f"Seek: position={start_position}s → chunk {start_chunk_idx}/{processor.total_chunks}, "
                f"offset={seek_offset:.2f}s"
            )

            # Check if WebSocket disconnected
            if not self._is_websocket_connected(websocket):
                logger.info(f"WebSocket disconnected, aborting seek stream")
                return

            # Send stream start message with seek info
            if not await self._send_stream_start_with_seek(
                websocket,
                track_id=track_id,
                preset=preset,
                intensity=intensity,
                sample_rate=processor.sample_rate,
                channels=processor.channels,
                total_chunks=processor.total_chunks,
                chunk_duration=processor.chunk_duration,
                total_duration=processor.duration,
                start_chunk=start_chunk_idx,
                seek_position=start_position,
                seek_offset=seek_offset,
            ):
                logger.info(f"WebSocket disconnected, cannot start seek stream")
                return

            # Process and stream chunks starting from start_chunk_idx
            for chunk_idx in range(start_chunk_idx, processor.total_chunks):
                if not self._is_websocket_connected(websocket):
                    logger.info(f"WebSocket disconnected, stopping seek stream")
                    break

                try:
                    # Process chunk with fast-start for first chunk of seek
                    fast_start = (chunk_idx == start_chunk_idx)
                    await self._process_and_stream_chunk(
                        chunk_idx, processor, websocket, on_progress
                    )

                    # Progress update
                    if on_progress:
                        chunks_remaining = processor.total_chunks - start_chunk_idx
                        chunks_done = chunk_idx - start_chunk_idx + 1
                        progress = (chunks_done / chunks_remaining) * 100
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
            logger.info(f"Seek stream complete: track={track_id}")
            await self._send_stream_end(
                websocket,
                track_id=track_id,
                total_samples=int(processor.duration * processor.sample_rate),
                duration=processor.duration,
            )

        except Exception as e:
            if "close message" in str(e).lower():
                logger.info(f"Seek streaming stopped: client disconnected")
            else:
                logger.error(f"Seek streaming failed: {e}", exc_info=True)
                if self._is_websocket_connected(websocket):
                    await self._send_error(websocket, track_id, str(e))
        finally:
            self._stream_semaphore.release()

    async def _send_stream_start_with_seek(
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
        start_chunk: int,
        seek_position: float,
        seek_offset: float,
    ) -> bool:
        """
        Send audio_stream_start message with seek information.

        Returns:
            True if message was sent, False if WebSocket was disconnected.
        """
        message: dict[str, Any] = {
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
                # Seek-specific fields
                "is_seek": True,
                "start_chunk": start_chunk,
                "seek_position": seek_position,
                "seek_offset": seek_offset,
                "stream_type": self._stream_type,
            },
        }
        if await self._safe_send(websocket, message):
            logger.debug(
                f"Sent stream_start (seek): chunk {start_chunk}/{total_chunks}, "
                f"position={seek_position}s"
            )
            return True
        return False
