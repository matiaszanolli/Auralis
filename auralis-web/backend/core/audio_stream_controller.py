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
import contextvars
import hashlib
import json
import logging
import threading
import uuid

# Per-task stream-type context variable (fixes #2493).
# Each asyncio Task inherits its own copy of the context, so concurrent
# stream_enhanced_audio / stream_normal_audio calls in different WebSocket
# handler tasks cannot overwrite each other's value — unlike self._stream_type.
_stream_type_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    '_stream_type', default=None
)
from collections import OrderedDict
from pathlib import Path
from typing import Any
from collections.abc import Callable

import numpy as np
from cache.manager import StreamlinedCacheManager
from core.chunked_processor import ChunkedAudioProcessor
from fastapi import WebSocket
from analysis.fingerprint_generator import FingerprintGenerator

from auralis.library.repositories.factory import RepositoryFactory

logger = logging.getLogger(__name__)

# Maximum number of encoded frames queued ahead of the WebSocket sender.
# Limits Python-heap memory when the client is slower than the encoder.
_SEND_QUEUE_MAXSIZE: int = 4

# Maximum number of concurrent audio streams (enhanced, normal, seek).
# Each stream holds a ChunkedProcessor in memory; unbounded concurrency
# causes OOM under load (issue #2185).
MAX_CONCURRENT_STREAMS: int = 10

# Module-level shared semaphore so the cap is enforced across ALL
# AudioStreamController instances (fixes #2469: per-instance semaphore
# was created fresh per request, making the cap non-functional).
_global_stream_semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)


class SimpleChunkCache:
    """Simple in-memory cache for processed audio chunks."""

    # Cache version - increment when chunk processing logic changes
    # This invalidates all cached chunks when we fix bugs in extraction/processing
    CACHE_VERSION = 3  # v3: Added _extract_chunk_segment to process_chunk for proper overlap handling

    def __init__(self, max_chunks: int = 50, max_memory_bytes: int = 512 * 1024 * 1024) -> None:
        """
        Initialize chunk cache.

        Args:
            max_chunks: Maximum number of chunks to keep in memory
            max_memory_bytes: Maximum total memory for cached audio (default 512 MB)
        """
        self.cache: OrderedDict[str, tuple[np.ndarray, int]] = OrderedDict()
        self.max_chunks: int = max_chunks
        self._max_memory_bytes: int = max_memory_bytes
        self._current_bytes: int = 0
        self._lock = threading.Lock()  # Protects cache from concurrent access (fixes #2436)

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
        with self._lock:
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
        with self._lock:
            key = self._make_key(track_id, chunk_idx, preset, intensity)

            chunk_bytes = audio.nbytes

            # Evict by count limit
            while len(self.cache) >= self.max_chunks:
                removed_key, (removed_audio, _) = self.cache.popitem(last=False)
                self._current_bytes -= removed_audio.nbytes

            # Evict by memory limit (#2084)
            while self._current_bytes + chunk_bytes > self._max_memory_bytes and self.cache:
                removed_key, (removed_audio, _) = self.cache.popitem(last=False)
                self._current_bytes -= removed_audio.nbytes

            self.cache[key] = (audio, sample_rate)
            self._current_bytes += chunk_bytes
            logger.debug(f"✅ Cached chunk {chunk_idx}, preset {preset}, cache size: {len(self.cache)}")

    def clear(self) -> None:
        """Clear all cached chunks."""
        with self._lock:
            self.cache.clear()
            self._current_bytes = 0

    def invalidate_chunk(self, track_id: int, chunk_idx: int, preset: str, intensity: float) -> None:
        """Remove a specific chunk from cache after a processing failure.

        Prevents a stale/corrupt cache entry from causing repeated failures on retry.

        Args:
            track_id: Track ID the chunk belongs to
            chunk_idx: Index of the failed chunk
            preset: Processing preset used
            intensity: Processing intensity used
        """
        with self._lock:
            key = self._make_key(track_id, chunk_idx, preset, intensity)
            if self.cache.pop(key, None) is not None:
                logger.debug(f"Invalidated stale cache entry: chunk {chunk_idx} of track {track_id}")


def ws_id(websocket: WebSocket) -> str:
    """Return a stable UUID for this websocket, assigned on first call.

    Using ws_id(websocket) is unsafe because CPython reuses memory addresses
    after GC, which could associate stale state with a new connection.
    """
    uid = getattr(websocket, '_auralis_id', None)
    if uid is None:
        uid = str(uuid.uuid4())
        websocket._auralis_id = uid  # type: ignore[attr-defined]
    return uid


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
        cache_manager: StreamlinedCacheManager | SimpleChunkCache | None = None,
        get_enhancement_enabled: Callable[[], bool] | None = None,
    ) -> None:
        """
        Initialize AudioStreamController.

        Args:
            chunked_processor_class: ChunkedAudioProcessor class for processing
            get_repository_factory: Callable that returns RepositoryFactory for track lookup
            cache_manager: Optional cache manager for chunk caching.
            get_enhancement_enabled: Callable that returns whether enhancement is currently
                enabled. The streaming loop checks this each iteration so toggling
                enhancement off stops in-flight chunks promptly (fixes #2866).
        """
        self.chunked_processor_class: type[ChunkedAudioProcessor] | None = chunked_processor_class
        self._get_repository_factory: Callable[[], RepositoryFactory] | None = get_repository_factory
        self._get_enhancement_enabled = get_enhancement_enabled

        # Use provided cache manager or fallback to SimpleChunkCache
        self.cache_manager: StreamlinedCacheManager | SimpleChunkCache = cache_manager or SimpleChunkCache()
        self._stream_type: str | None = None  # Deprecated; reads now use _stream_type_var.get() (fixes #2493)
        logger.info(f"AudioStreamController initialized with cache manager: {type(self.cache_manager).__name__}")

        # NEW (Phase 7.3): Fingerprint generator for on-demand generation
        self.fingerprint_generator: FingerprintGenerator | None = None
        self.fingerprint_init_error: str | None = None
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
                    self.fingerprint_init_error = "RepositoryFactory missing session_factory attribute"
                    logger.warning(f"Fingerprint generation unavailable: {self.fingerprint_init_error}")
            except Exception as e:
                self.fingerprint_init_error = str(e)
                logger.warning(f"Failed to initialize FingerprintGenerator: {e}, proceeding without on-demand fingerprint generation")

        self.active_streams: dict[str, Any] = {}  # ws_id(websocket) -> streaming task
        self._active_streams_lock: asyncio.Lock = asyncio.Lock()  # Protects active_streams (#3182)
        # Use the module-level semaphore shared across all instances (fixes #2469)
        self._stream_semaphore: asyncio.Semaphore = _global_stream_semaphore

        # Store previous chunk tails for crossfading (track_id -> tail samples).
        # _chunk_tails_lock serialises the check-then-set sequence so that if the
        # architecture ever reuses a controller across concurrent seek tasks the
        # crossfade state cannot be torn (fixes #2326).
        self._chunk_tails: dict[int, np.ndarray] = {}
        self._chunk_tails_lock: asyncio.Lock = asyncio.Lock()

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

    async def _safe_send_bytes(self, websocket: WebSocket, data: bytes) -> bool:
        """Safely send binary data to WebSocket, handling disconnection gracefully."""
        if not self._is_websocket_connected(websocket):
            logger.debug("WebSocket disconnected, skipping binary send")
            return False
        try:
            await websocket.send_bytes(data)
            return True
        except RuntimeError as e:
            if "close message" in str(e).lower():
                logger.debug(f"WebSocket closed during binary send: {e}")
            else:
                logger.warning(f"WebSocket binary send failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error sending WebSocket binary: {e}")
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
                from analysis.fingerprint_queue import get_fingerprint_queue
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
        _stream_type_var.set("enhanced")  # per-task; safe for concurrent coroutines (fixes #2493)

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
            track = await asyncio.to_thread(factory.tracks.get_by_id, track_id)
            if not track:
                await self._send_error(websocket, track_id, "Track not found")
                self._stream_semaphore.release()
                return

            if not Path(track.filepath).exists():
                await self._send_error(
                    websocket, track_id, "Audio file not found"
                )
                self._stream_semaphore.release()
                return
        except Exception as e:
            logger.error(f"Failed to load track {track_id}: {e}", exc_info=True)
            await self._send_error(websocket, track_id, "Failed to load track")
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

            # Ensure processor has loaded metadata (raise instead of assert
            # so guards work under python -O / PyInstaller, fixes #2735)
            for _attr in ('total_chunks', 'sample_rate', 'channels', 'duration'):
                if getattr(processor, _attr) is None:
                    raise ValueError(f"Processor metadata missing: {_attr} is None")

            # Register active stream so cleanup can always find it (fixes #2076, #3182)
            async with self._active_streams_lock:
                self.active_streams[ws_id(websocket)] = asyncio.current_task()

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

            # Process and stream chunks with look-ahead: start processing
            # chunk N+1 while streaming chunk N to eliminate inter-chunk gaps.
            lookahead_task: asyncio.Task[tuple[np.ndarray, int]] | None = None
            next_track_prefetched: bool = False

            for chunk_idx in range(processor.total_chunks):
                # Stop streaming if enhancement was toggled off mid-stream (fixes #2866).
                if self._get_enhancement_enabled and not self._get_enhancement_enabled():
                    logger.info(
                        f"Enhancement disabled mid-stream, stopping enhanced stream for track {track_id}"
                    )
                    if lookahead_task and not lookahead_task.done():
                        lookahead_task.cancel()
                    break

                # Honour pause/resume events from the WebSocket handler (#2106).
                from routers.system import _stream_pause_events, _stream_flow_events
                pause_evt = _stream_pause_events.get(ws_id(websocket))
                if pause_evt is not None:
                    await pause_evt.wait()
                # Honour flow control: wait if frontend buffer is full.
                flow_evt = _stream_flow_events.get(ws_id(websocket))
                if flow_evt is not None:
                    await flow_evt.wait()

                if not self._is_websocket_connected(websocket):
                    logger.info(f"WebSocket disconnected, stopping stream")
                    if lookahead_task and not lookahead_task.done():
                        lookahead_task.cancel()
                    break

                try:
                    # Get processed chunk: from look-ahead task or process now
                    if lookahead_task is not None:
                        try:
                            pcm_samples, _sr = await lookahead_task
                        except ConnectionError:
                            # Client disconnected during look-ahead processing
                            break
                        lookahead_task = None
                    else:
                        pcm_samples, _sr = await self._process_chunk_only(
                            chunk_idx, processor, websocket
                        )

                    # Start look-ahead: process next chunk while we stream current one
                    if chunk_idx + 1 < processor.total_chunks:
                        lookahead_task = asyncio.create_task(
                            self._process_chunk_only(
                                chunk_idx + 1, processor, websocket
                            )
                        )

                    # Stream current chunk (crossfade + send)
                    await self._stream_processed_chunk(
                        pcm_samples, chunk_idx, processor, websocket
                    )

                    # Progress update
                    progress = ((chunk_idx + 1) / processor.total_chunks) * 100
                    if on_progress:
                        await on_progress(track_id, progress, f"Processed chunk {chunk_idx + 1}")

                    # Pre-fetch next track at 80% to eliminate cold-start on transitions
                    if progress >= 80 and not next_track_prefetched:
                        next_track_prefetched = True
                        asyncio.create_task(
                            self._prefetch_next_track(track_id, preset, intensity)
                        )

                except ConnectionError:
                    # Client disconnected — clean exit
                    if lookahead_task and not lookahead_task.done():
                        lookahead_task.cancel()
                    break

                except Exception as chunk_error:
                    # Cancel look-ahead task on error
                    if lookahead_task and not lookahead_task.done():
                        lookahead_task.cancel()
                    logger.error(
                        f"Failed to process chunk {chunk_idx}: {chunk_error}",
                        exc_info=True
                    )
                    # Compute recovery position: start of the failed chunk (issue #2085)
                    recovery_position: float = chunk_idx * processor.chunk_interval
                    # Evict any stale cache entry for the failed chunk so a retry
                    # processes it fresh rather than replaying corrupt data (issue #2085)
                    if isinstance(self.cache_manager, SimpleChunkCache):
                        self.cache_manager.invalidate_chunk(
                            track_id=track_id,
                            chunk_idx=chunk_idx,
                            preset=preset,
                            intensity=intensity,
                        )
                    # Proactively remove crossfade tail so the next chunk starts clean
                    self._chunk_tails.pop(track_id, None)
                    await self._send_error(
                        websocket,
                        track_id,
                        f"Failed to process audio chunk {chunk_idx}",
                        recovery_position=recovery_position,
                    )
                    # Skip failed chunk and continue with remaining chunks (#3190)
                    continue

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
                    await self._send_error(websocket, track_id, "Audio streaming failed")
        finally:
            # Clean up chunk tail storage for this track
            self._chunk_tails.pop(track_id, None)
            async with self._active_streams_lock:  # fixes #2076, #3182
                self.active_streams.pop(ws_id(websocket), None)
            self._stream_semaphore.release()

    async def stream_normal_audio(
        self,
        track_id: int,
        websocket: WebSocket,
        start_position: float = 0.0,
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
        _stream_type_var.set("normal")  # per-task; safe for concurrent coroutines (fixes #2493)

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
            track = await asyncio.to_thread(factory.tracks.get_by_id, track_id)
            if not track:
                await self._send_error(websocket, track_id, "Track not found")
                self._stream_semaphore.release()
                return

            if not Path(track.filepath).exists():
                await self._send_error(
                    websocket, track_id, "Audio file not found"
                )
                self._stream_semaphore.release()
                return
        except Exception as e:
            logger.error(f"Failed to load track {track_id}: {e}", exc_info=True)
            await self._send_error(websocket, track_id, "Failed to load track")
            self._stream_semaphore.release()
            return

        # For compressed formats (MP3, M4A, etc.), convert to temp WAV first
        # since sf.SoundFile only supports PCM formats (#3225).
        temp_wav_path: str | None = None
        streaming_filepath = str(track.filepath)

        try:
            from auralis.io.unified_loader import FFMPEG_FORMATS
            file_ext = Path(track.filepath).suffix.lower()
            if file_ext in FFMPEG_FORMATS:
                import tempfile
                from auralis.io.unified_loader import load_audio
                temp_dir = tempfile.mkdtemp(prefix='auralis_stream_')
                audio_data, sr = await asyncio.to_thread(
                    load_audio, str(track.filepath), "audio", temp_dir
                )
                # Write to temp WAV for chunked streaming
                temp_wav_path = str(Path(temp_dir) / 'stream.wav')
                import soundfile as _sf
                await asyncio.to_thread(
                    _sf.write, temp_wav_path, audio_data, sr, format='WAV', subtype='FLOAT'
                )
                streaming_filepath = temp_wav_path
                logger.info(f"Converted {file_ext} to temp WAV for normal streaming")

            # Read file metadata only — do NOT load audio data yet (#2121).
            # sf.read() would allocate ~200 MB for a 10-min stereo track; instead
            # we open the SoundFile, record its shape, and close it immediately.
            def _get_audio_info(filepath: str) -> tuple[int, int, int]:
                with sf.SoundFile(filepath) as audio_file:
                    return audio_file.samplerate, audio_file.channels, len(audio_file)

            sample_rate, channels, total_frames = await asyncio.to_thread(
                _get_audio_info, streaming_filepath
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

            # Calculate start chunk for seek (#3187)
            start_chunk = 0
            if start_position > 0:
                start_sample = int(start_position * sample_rate)
                start_chunk = min(start_sample // interval_samples, total_chunks - 1)
            remaining_chunks = total_chunks - start_chunk

            # Register active stream so cleanup can always find it (fixes #2076, #3182)
            async with self._active_streams_lock:
                self.active_streams[ws_id(websocket)] = asyncio.current_task()

            logger.info(
                f"Starting normal audio stream: track={track_id}, "
                f"duration={duration:.1f}s, chunks={total_chunks}, sr={sample_rate}Hz"
                + (f", seek={start_position:.1f}s (chunk {start_chunk})" if start_chunk > 0 else "")
            )

            # Send stream start message (report remaining chunks for seek)
            if not await self._send_stream_start(
                websocket,
                track_id=track_id,
                preset="none",  # No processing
                intensity=1.0,   # Full intensity (original)
                sample_rate=sample_rate,
                channels=channels,
                total_chunks=remaining_chunks,
                chunk_duration=chunk_duration,
                total_duration=duration - (start_chunk * chunk_duration),
            ):
                logger.info(f"WebSocket disconnected, cannot start stream")
                return

            # Helper: open → seek → read → close for a single chunk (#2121).
            # Uses streaming_filepath (temp WAV for compressed formats, original for PCM).
            def _read_audio_chunk(filepath: str, start: int, frames: int) -> np.ndarray:
                with sf.SoundFile(filepath) as audio_file:
                    audio_file.seek(start)
                    # always_2d=True: mono returned as (N, 1) matching stereo shape
                    # Do NOT use fill_value: send the last chunk at its actual
                    # length to avoid appending silence (#2124).
                    return audio_file.read(
                        frames=frames, dtype='float32', always_2d=True
                    )

            # Stream chunks with look-ahead: read chunk N+1 from disk while
            # streaming chunk N to eliminate I/O gaps.
            lookahead_read: asyncio.Task[np.ndarray] | None = None

            for chunk_idx in range(start_chunk, total_chunks):
                # Honour pause/resume events from the WebSocket handler (#2106).
                from routers.system import _stream_pause_events, _stream_flow_events
                pause_evt = _stream_pause_events.get(ws_id(websocket))
                if pause_evt is not None:
                    await pause_evt.wait()
                # Honour flow control: wait if frontend buffer is full.
                flow_evt = _stream_flow_events.get(ws_id(websocket))
                if flow_evt is not None:
                    await flow_evt.wait()

                if not self._is_websocket_connected(websocket):
                    logger.info(f"WebSocket disconnected, stopping stream")
                    if lookahead_read and not lookahead_read.done():
                        lookahead_read.cancel()
                    break

                try:
                    # Get chunk audio: from look-ahead task or read now
                    if lookahead_read is not None:
                        chunk_audio = await lookahead_read
                        lookahead_read = None
                    else:
                        start_sample = chunk_idx * interval_samples
                        chunk_audio = await asyncio.to_thread(
                            _read_audio_chunk, streaming_filepath, start_sample, chunk_samples
                        )

                    # Start look-ahead: read next chunk while we stream current one
                    if chunk_idx + 1 < total_chunks:
                        next_start = (chunk_idx + 1) * interval_samples
                        lookahead_read = asyncio.create_task(
                            asyncio.to_thread(
                                _read_audio_chunk, streaming_filepath, next_start, chunk_samples
                            )
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
                    if lookahead_read and not lookahead_read.done():
                        lookahead_read.cancel()
                    logger.error(f"Failed to stream chunk {chunk_idx}: {chunk_error}", exc_info=True)
                    # Recovery position: start of the failed chunk (issue #2085)
                    normal_recovery_position: float = chunk_idx * chunk_duration
                    await self._send_error(
                        websocket,
                        track_id,
                        f"Failed to stream audio chunk {chunk_idx}",
                        recovery_position=normal_recovery_position,
                    )
                    # Skip failed chunk and continue with remaining chunks (#3190)
                    continue

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
                    await self._send_error(websocket, track_id, "Audio streaming failed")
        finally:
            async with self._active_streams_lock:  # fixes #2076, #3182
                self.active_streams.pop(ws_id(websocket), None)
            self._stream_semaphore.release()
            # Clean up temp WAV created for compressed format streaming (#3225)
            if temp_wav_path:
                import shutil
                try:
                    shutil.rmtree(Path(temp_wav_path).parent, ignore_errors=True)
                except Exception:
                    pass

    async def _process_chunk_only(
        self,
        chunk_index: int,
        processor: ChunkedAudioProcessor,
        websocket: WebSocket | None = None,
    ) -> tuple[np.ndarray, int]:
        """
        Process a single chunk (cache check + DSP) without streaming.

        Returns the processed PCM samples and sample rate. Used by the
        look-ahead pipeline so chunk N+1 can be processed while chunk N
        is being streamed.

        Args:
            chunk_index: Index of chunk to process (0-based)
            processor: ChunkedProcessor instance
            websocket: Optional WebSocket for disconnect guard

        Returns:
            Tuple of (pcm_samples, sample_rate)
        """
        fast_start: bool = chunk_index == 0

        logger.debug(
            f"Processing chunk {chunk_index}/{processor.total_chunks} "
            f"(fast_start={fast_start})"
        )

        # Try to get from cache first
        pcm_samples: np.ndarray | None = None
        sr: int | None = None

        try:
            if isinstance(self.cache_manager, SimpleChunkCache):
                cached_result: tuple[np.ndarray, int] | None = self.cache_manager.get(
                    track_id=processor.track_id,
                    chunk_idx=chunk_index,
                    preset=processor.preset,
                    intensity=processor.intensity
                )
                if cached_result:
                    pcm_samples, sr = cached_result
                    logger.info(f"Cache HIT: chunk {chunk_index}, preset {processor.preset}")
        except Exception as e:
            logger.debug(f"Cache lookup failed (not critical): {e}")

        # Process chunk if not cached
        if pcm_samples is None:
            # Guard: don't waste CPU on DSP if the client disconnected (fixes #2076)
            if websocket is not None and not self._is_websocket_connected(websocket):
                raise ConnectionError(f"WebSocket disconnected before processing chunk {chunk_index}")
            logger.debug(f"Cache MISS: Processing chunk {chunk_index}")
            _chunk_path, pcm_samples = await processor.process_chunk_safe(chunk_index, fast_start=fast_start)
            sr = processor.sample_rate

            logger.debug(
                f"Chunk {chunk_index}: processed {len(pcm_samples)} samples at {sr}Hz"
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

        assert pcm_samples is not None
        assert sr is not None
        return pcm_samples, sr

    async def _stream_processed_chunk(
        self,
        pcm_samples: np.ndarray,
        chunk_index: int,
        processor: ChunkedAudioProcessor,
        websocket: WebSocket,
    ) -> None:
        """
        Apply crossfade and stream already-processed PCM samples to client.

        Args:
            pcm_samples: Processed PCM audio array
            chunk_index: Index of this chunk
            processor: ChunkedProcessor instance (for metadata)
            websocket: WebSocket connection
        """
        if processor.total_chunks is None:
            raise ValueError("Processor metadata missing: total_chunks is None")
        if processor.sample_rate is None:
            raise ValueError("Processor metadata missing: sample_rate is None")

        # Apply server-side crossfade to smooth chunk boundaries
        crossfade_duration_ms = 200  # milliseconds
        crossfade_samples = int(crossfade_duration_ms * processor.sample_rate / 1000)

        # _chunk_tails_lock serialises the read-check-write so concurrent
        # seeks for the same track_id cannot produce a torn tail (fixes #2326).
        async with self._chunk_tails_lock:
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

        # Server already applied the boundary crossfade above; send 0 so the
        # client does not double-apply it (fixes #2188: double crossfade).
        await self._send_pcm_chunk(
            websocket,
            pcm_samples=pcm_samples,
            chunk_index=chunk_index,
            total_chunks=processor.total_chunks,
            crossfade_samples=0,
        )

    async def _process_and_stream_chunk(
        self,
        chunk_index: int,
        processor: ChunkedAudioProcessor,
        websocket: WebSocket,
        on_progress: Callable[[int, float, str], Any] | None = None,
    ) -> None:
        """Process single chunk and stream PCM samples to client (legacy entry point)."""
        pcm_samples, _sr = await self._process_chunk_only(chunk_index, processor, websocket)
        await self._stream_processed_chunk(pcm_samples, chunk_index, processor, websocket)

    async def _prefetch_next_track(
        self,
        current_track_id: int,
        preset: str,
        intensity: float,
    ) -> None:
        """
        Pre-process the first chunk of the next track in queue.

        Called at ~80% progress of the current track to eliminate cold-start
        delay on track transitions. Silently fails — this is an optimization,
        not a requirement.

        Populates the chunk cache so next track's chunk 0 is a cache hit, and
        queues fingerprint generation in background.
        """
        if not self._get_repository_factory or not self.chunked_processor_class:
            return

        try:
            factory = self._get_repository_factory()
            queue_state = factory.queue.get_queue_state()
            if not queue_state or not queue_state.track_ids:
                return

            # Parse track IDs and find next track
            import json as _json
            track_ids: list[int] = _json.loads(queue_state.track_ids)
            if not track_ids:
                return

            current_idx = queue_state.current_index
            # Find the current track in the queue
            try:
                pos = track_ids.index(current_track_id)
                next_idx = pos + 1
            except ValueError:
                # Current track not in queue — use current_index + 1
                next_idx = current_idx + 1

            if next_idx >= len(track_ids):
                # Check repeat mode
                if queue_state.repeat_mode == 'all':
                    next_idx = 0
                else:
                    return  # No next track

            next_track_id = track_ids[next_idx]
            next_track = await asyncio.to_thread(factory.tracks.get_by_id, next_track_id)
            if not next_track or not Path(next_track.filepath).exists():
                return

            logger.info(f"Pre-fetching next track {next_track_id} (chunk 0)")

            # Queue fingerprint generation in background
            await self._check_or_queue_fingerprint(
                track_id=next_track_id,
                filepath=str(next_track.filepath),
                websocket=None,
            )

            # Check if chunk 0 is already cached
            if isinstance(self.cache_manager, SimpleChunkCache):
                cached = self.cache_manager.get(
                    track_id=next_track_id, chunk_idx=0,
                    preset=preset, intensity=intensity,
                )
                if cached:
                    logger.info(f"Next track {next_track_id} chunk 0 already cached")
                    return

            # Clear any stale tail from a previous play of this track
            self._chunk_tails.pop(next_track_id, None)

            # Create processor and process chunk 0 (populates cache)
            processor = await asyncio.to_thread(
                self.chunked_processor_class,
                track_id=next_track_id,
                filepath=str(next_track.filepath),
                preset=preset,
                intensity=intensity,
            )
            await self._process_chunk_only(0, processor)
            logger.info(f"Pre-fetched next track {next_track_id} chunk 0 into cache")

        except Exception as e:
            # Silent failure — prefetch is an optimization
            logger.debug(f"Next-track prefetch failed (not critical): {e}")

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

        # The previous chunk was already sent in full (including its tail),
        # so mixing prev_tail into the current head would duplicate those
        # samples as audible pre-echo. Instead, just fade IN the current
        # chunk's head to smooth the energy transition at the boundary.
        fade_in = np.sin(np.linspace(0, np.pi / 2, actual_crossfade)) ** 2

        # Handle stereo
        if current_chunk.ndim == 2:
            fade_in = fade_in[:, np.newaxis]

        result = current_chunk.copy()
        result[:actual_crossfade] *= fade_in

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
        Send PCM samples to client as binary WebSocket frames.

        Each frame is preceded by a JSON metadata message (audio_chunk_meta)
        followed by the raw PCM bytes as a binary frame. This avoids the 33%
        overhead of base64 encoding while keeping metadata structured.

        Splits large PCM data into multiple frame pairs to stay below the
        WebSocket 1MB frame limit (~300KB raw per frame).

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

        # Split into smaller frames to avoid WebSocket 1MB frame limit.
        # Each float32 sample = 4 bytes. Target ~300KB raw per binary frame.
        #
        # Flatten to 1D first so that len() and slicing always operate on
        # individual float32 values rather than rows (fixes #2257: for stereo
        # 2D arrays len() returned frame-count, producing ~800KB frames).
        TARGET_FRAME_BYTES: int = 300 * 1024  # 300 KB raw (was 400KB base64)
        BYTES_PER_SAMPLE: int = 4  # float32
        pcm_flat: np.ndarray = pcm_samples.reshape(-1)
        samples_per_frame: int = TARGET_FRAME_BYTES // BYTES_PER_SAMPLE

        total_samples: int = len(pcm_flat)
        num_frames: int = (total_samples + samples_per_frame - 1) // samples_per_frame

        stream_type = _stream_type_var.get()

        # Bounded producer/consumer: limits Python-heap accumulation when the
        # client is slower than the sender (backpressure for issue #2122).
        # Each item is a (metadata_dict, pcm_bytes) tuple; the consumer sends
        # the JSON metadata first, then the binary frame. On disconnect it
        # signals the producer to stop.
        queue: asyncio.Queue[tuple[dict[str, Any], bytes] | None] = asyncio.Queue(
            maxsize=_SEND_QUEUE_MAXSIZE
        )
        abort_event: asyncio.Event = asyncio.Event()

        # Monotonic sequence counter for text+binary frame pairing.
        # The client can use this to detect desync if frames are ever
        # dropped or reordered (fixes #3189).
        frame_seq = 0

        async def _producer() -> None:
            nonlocal frame_seq
            try:
                for frame_idx in range(num_frames):
                    if abort_event.is_set():
                        break
                    start_idx: int = frame_idx * samples_per_frame
                    end_idx: int = min(start_idx + samples_per_frame, total_samples)
                    frame_samples: np.ndarray = pcm_flat[start_idx:end_idx]

                    metadata: dict[str, Any] = {
                        "type": "audio_chunk_meta",
                        "data": {
                            "seq": frame_seq,
                            "chunk_index": chunk_index,
                            "chunk_count": total_chunks,
                            "frame_index": frame_idx,
                            "frame_count": num_frames,
                            "sample_count": frame_samples.size,
                            "crossfade_samples": crossfade_samples,
                            "stream_type": stream_type,
                        },
                    }
                    frame_seq += 1
                    pcm_bytes: bytes = frame_samples.astype('<f4').tobytes()
                    await queue.put((metadata, pcm_bytes))
            finally:
                await queue.put(None)  # sentinel

        async def _consumer() -> None:
            while True:
                item = await queue.get()
                if item is None:
                    break
                metadata, pcm_bytes = item
                # Send JSON metadata first, then raw binary PCM
                sent: bool = await self._safe_send(websocket, metadata)
                if not sent:
                    abort_event.set()
                    while not queue.empty():
                        queue.get_nowait()
                    break
                sent = await self._safe_send_bytes(websocket, pcm_bytes)
                if not sent:
                    abort_event.set()
                    while not queue.empty():
                        queue.get_nowait()
                    break
                frame_idx = metadata["data"]["frame_index"]
                logger.debug(
                    f"Streamed chunk {chunk_index} frame {frame_idx}/{num_frames}: "
                    f"{metadata['data']['sample_count']} samples ({len(pcm_bytes)} bytes)"
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
                "stream_type": _stream_type_var.get(),
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
                "stream_type": _stream_type_var.get(),
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
        error_code: str = "STREAMING_ERROR",
    ) -> None:
        """Send audio_stream_error message to client.

        Args:
            websocket: WebSocket connection to send the error to
            track_id: ID of the track that failed
            error_message: Human-readable error description
            recovery_position: Seconds into the track from which the client may
                seek/retry (set when a specific chunk fails, issue #2085).
            error_code: Machine-readable error code for frontend recovery logic
        """
        if not self._is_websocket_connected(websocket):
            return

        data: dict[str, Any] = {
            "track_id": track_id,
            "error": error_message,
            "code": error_code,
            "stream_type": _stream_type_var.get(),
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
                "stream_type": _stream_type_var.get(),
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
        _stream_type_var.set("enhanced")  # per-task; safe for concurrent coroutines (fixes #2493)

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
            track = await asyncio.to_thread(factory.tracks.get_by_id, track_id)
            if not track:
                await self._send_error(websocket, track_id, "Track not found")
                self._stream_semaphore.release()
                return

            if not Path(track.filepath).exists():
                await self._send_error(
                    websocket, track_id, "Audio file not found"
                )
                self._stream_semaphore.release()
                return
        except Exception as e:
            logger.error(f"Failed to load track {track_id}: {e}", exc_info=True)
            await self._send_error(websocket, track_id, "Failed to load track")
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
                await self._send_error(websocket, track_id, error_msg, error_code="SEEK_ERROR")
                return

            # Ensure processor has loaded metadata (raise instead of assert
            # so guards work under python -O / PyInstaller, fixes #2735)
            for _attr in ('total_chunks', 'sample_rate', 'channels', 'duration'):
                if getattr(processor, _attr) is None:
                    raise ValueError(f"Processor metadata missing: {_attr} is None")

            # Register active stream so cleanup can always find it (fixes #2076, #3182)
            async with self._active_streams_lock:
                self.active_streams[ws_id(websocket)] = asyncio.current_task()

            # Calculate which chunk to start from based on position
            # Chunks overlap, so we need to find the chunk that contains this position
            chunk_interval = processor.chunk_interval
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

            # Process and stream chunks with look-ahead (same pattern as
            # normal streaming): process chunk N+1 while streaming chunk N
            # to eliminate inter-chunk gaps on slow storage.
            lookahead_task: asyncio.Task[tuple[np.ndarray, int]] | None = None

            for chunk_idx in range(start_chunk_idx, processor.total_chunks):
                # Stop streaming if enhancement was toggled off mid-stream (fixes #2866).
                if self._get_enhancement_enabled and not self._get_enhancement_enabled():
                    logger.info(
                        f"Enhancement disabled mid-stream, stopping seek stream for track {track_id}"
                    )
                    if lookahead_task and not lookahead_task.done():
                        lookahead_task.cancel()
                    break

                # Honour pause/resume and flow control events (fixes missing
                # pause check in seek path — pre-existing bug).
                from routers.system import _stream_pause_events, _stream_flow_events
                pause_evt = _stream_pause_events.get(ws_id(websocket))
                if pause_evt is not None:
                    await pause_evt.wait()
                flow_evt = _stream_flow_events.get(ws_id(websocket))
                if flow_evt is not None:
                    await flow_evt.wait()

                if not self._is_websocket_connected(websocket):
                    logger.info(f"WebSocket disconnected, stopping seek stream")
                    if lookahead_task and not lookahead_task.done():
                        lookahead_task.cancel()
                    break

                try:
                    # Get processed chunk: from look-ahead task or process now
                    if lookahead_task is not None:
                        try:
                            pcm_samples, _sr = await lookahead_task
                        except ConnectionError:
                            break
                        lookahead_task = None
                    else:
                        pcm_samples, _sr = await self._process_chunk_only(
                            chunk_idx, processor, websocket
                        )

                    # Trim the first chunk to the exact seek position
                    if chunk_idx == start_chunk_idx and seek_offset > 0:
                        trim_samples = round(seek_offset * processor.sample_rate)
                        pcm_samples = pcm_samples[trim_samples:]
                        logger.debug(
                            f"Seek trim: removed {trim_samples} samples "
                            f"({seek_offset:.2f}s) from chunk {chunk_idx}"
                        )

                    # Start look-ahead: process next chunk while we stream current one
                    if chunk_idx + 1 < processor.total_chunks:
                        lookahead_task = asyncio.create_task(
                            self._process_chunk_only(
                                chunk_idx + 1, processor, websocket
                            )
                        )

                    # Stream current chunk (crossfade + send)
                    await self._stream_processed_chunk(
                        pcm_samples, chunk_idx, processor, websocket
                    )

                    # Progress update
                    if on_progress:
                        chunks_remaining = processor.total_chunks - start_chunk_idx
                        chunks_done = chunk_idx - start_chunk_idx + 1
                        progress = (chunks_done / chunks_remaining) * 100
                        await on_progress(track_id, progress, f"Processed chunk {chunk_idx + 1}")

                except ConnectionError:
                    if lookahead_task and not lookahead_task.done():
                        lookahead_task.cancel()
                    break

                except Exception as chunk_error:
                    if lookahead_task and not lookahead_task.done():
                        lookahead_task.cancel()
                    logger.error(
                        f"Failed to process chunk {chunk_idx}: {chunk_error}",
                        exc_info=True
                    )
                    recovery_position = chunk_idx * chunk_interval
                    await self._send_error(
                        websocket,
                        track_id,
                        f"Failed to process audio chunk {chunk_idx}",
                        recovery_position=recovery_position,
                    )
                    # Skip failed chunk and continue (#3190)
                    continue

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
                    await self._send_error(websocket, track_id, "Audio streaming failed")
        finally:
            self._chunk_tails.pop(track_id, None)  # fixes orphaned state
            async with self._active_streams_lock:  # fixes #2076, #3182
                self.active_streams.pop(ws_id(websocket), None)
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
                "stream_type": _stream_type_var.get(),
            },
        }
        if await self._safe_send(websocket, message):
            logger.debug(
                f"Sent stream_start (seek): chunk {start_chunk}/{total_chunks}, "
                f"position={seek_position}s"
            )
            return True
        return False
