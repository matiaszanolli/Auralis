#!/usr/bin/env python3

"""
Audio Stream Controller
~~~~~~~~~~~~~~~~~~~~~~~

Manages real-time audio streaming via WebSocket for enhanced audio playback.
Unified architecture: single WebSocket endpoint for all audio streaming.

This module holds the AudioStreamController orchestrator plus the shared
module-level state (contextvars, timeouts, semaphore) the extracted
streaming submodules key off of: chunk_cache.py (SimpleChunkCache),
stream_protocol.py (wire send + PCM framing), stream_messages.py (JSON
control messages), stream_fingerprint.py (fingerprint readiness),
stream_chunk_ops.py + stream_prefetch.py (per-chunk helpers), and
stream_enhanced.py / stream_normal.py / stream_seek.py (the three entry
points).

AudioStreamController's methods are thin delegates to these submodules so
the public/test-facing surface (`controller._send_error(...)`,
`patch.object(controller, "_send_stream_start", ...)`, etc.) is unchanged
(#4071 — god-file split of what was previously a single 2016-line file).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import contextvars
import logging
import uuid
from typing import Any
from collections.abc import Callable

import numpy as np
from cache.manager import StreamlinedCacheManager
from core.chunked_processor import ChunkedAudioProcessor
from fastapi import WebSocket
from analysis.fingerprint_generator import FingerprintGenerator

from auralis.library.repositories.factory import RepositoryFactory

from .chunk_cache import SimpleChunkCache
from .env_config import get_int_env
from .stream_protocol import _SEND_QUEUE_MAXSIZE  # noqa: F401 (re-exported for compat)

logger = logging.getLogger(__name__)

# Per-task stream-type context variable (fixes #2493).
# Each asyncio Task inherits its own copy of the context, so concurrent
# stream_enhanced_audio / stream_normal_audio calls in different WebSocket
# handler tasks cannot overwrite each other's value — unlike self._stream_type.
_stream_type_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    '_stream_type', default=None
)

# Per-stream monotonic frame counter (fixes #3841). Like _stream_type_var, this
# is a ContextVar so concurrent streams in different WebSocket tasks each keep
# their own counter instead of clobbering shared instance state (the #2493 bug).
#
# It holds a ONE-ELEMENT LIST used as a mutable cell, not a bare int:
# stream_protocol.send_pcm_chunk runs its frame producer in a COPIED context
# (via asyncio.gather), so the producer must MUTATE a shared object
# (cell[0] += 1) rather than rebind the var with .set() — only mutation is
# visible back in the parent stream task. That is what lets `seq` stay
# monotonic ACROSS chunk boundaries for the whole stream, as the client
# contract (AudioChunkMetaMessage JSDoc) promises. stream_messages.send_stream_start
# resets the cell to [0] at every audio_stream_start boundary.
_frame_seq_var: contextvars.ContextVar[list[int] | None] = contextvars.ContextVar(
    '_frame_seq', default=None
)

# Maximum number of concurrent audio streams (enhanced, normal, seek).
# Each stream holds a ChunkedProcessor in memory; unbounded concurrency
# causes OOM under load (issue #2185). Override via AURALIS_MAX_CONCURRENT_STREAMS
# for deployments beyond the default single-user desktop scope (#3917) — see
# auralis-web/backend/CONFIG.md.
MAX_CONCURRENT_STREAMS: int = get_int_env("AURALIS_MAX_CONCURRENT_STREAMS", 10)

# Module-level shared semaphore so the cap is enforced across ALL
# AudioStreamController instances (fixes #2469: per-instance semaphore
# was created fresh per request, making the cap non-functional).
_global_stream_semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)

# Per-chunk DSP timeout. process_chunk_safe is offloaded to a thread, so a
# hung DSP call (pathological buffer / Rust DSP deadlock) would otherwise
# wedge the per-stream coroutine forever — blocking pause/resume, never
# firing chunk-error recovery, and holding the stream semaphore slot until
# the client disconnects. Bounding it lets the failure flow into the normal
# skip-failed-chunk recovery branch (sibling of #2747, fixes #3852).
CHUNK_PROCESS_TIMEOUT: float = 30.0


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

    All streaming logic lives in the stream_* submodules (see module
    docstring); this class wires them to per-instance state.
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
        from . import stream_protocol
        return stream_protocol.is_websocket_connected(websocket)

    async def _safe_send(self, websocket: WebSocket, message: dict[str, Any]) -> bool:
        from . import stream_protocol
        return await stream_protocol.safe_send(self, websocket, message)

    async def _safe_send_bytes(self, websocket: WebSocket, data: bytes) -> bool:
        from . import stream_protocol
        return await stream_protocol.safe_send_bytes(self, websocket, data)

    async def _send_pcm_chunk(
        self,
        websocket: WebSocket,
        pcm_samples: np.ndarray,
        chunk_index: int,
        total_chunks: int,
        crossfade_samples: int,
    ) -> None:
        from . import stream_protocol
        await stream_protocol.send_pcm_chunk(
            self, websocket, pcm_samples, chunk_index, total_chunks, crossfade_samples
        )

    async def _send_stream_start(self, websocket: WebSocket, **kwargs: Any) -> bool:
        from . import stream_messages
        return await stream_messages.send_stream_start(self, websocket, **kwargs)

    async def _send_stream_end(self, websocket: WebSocket, **kwargs: Any) -> bool:
        from . import stream_messages
        return await stream_messages.send_stream_end(self, websocket, **kwargs)

    async def _send_error(self, websocket: WebSocket, track_id: int, error_message: str, **kwargs: Any) -> None:
        from . import stream_messages
        await stream_messages.send_error(self, websocket, track_id, error_message, **kwargs)

    async def _send_fingerprint_progress(
        self, websocket: WebSocket, track_id: int, status: str, message: str
    ) -> None:
        from . import stream_messages
        await stream_messages.send_fingerprint_progress(websocket, track_id, status, message)


    async def _ensure_fingerprint_available(
        self, track_id: int, filepath: str, websocket: WebSocket | None = None
    ) -> bool:
        from . import stream_fingerprint
        return await stream_fingerprint.ensure_fingerprint_available(self, track_id, filepath, websocket)

    async def _check_or_queue_fingerprint(
        self, track_id: int, filepath: str, websocket: WebSocket | None = None
    ) -> bool:
        from . import stream_fingerprint
        return await stream_fingerprint.check_or_queue_fingerprint(self, track_id, filepath, websocket)


    async def _drop_chunk_tail(self, track_id: int) -> None:
        from . import stream_chunk_ops
        await stream_chunk_ops.drop_chunk_tail(self, track_id)

    @staticmethod
    async def _drain_cancelled_task(task: 'asyncio.Task[Any] | None') -> None:
        from . import stream_chunk_ops
        await stream_chunk_ops.drain_cancelled_task(task)

    async def _process_chunk_only(
        self, chunk_index: int, processor: ChunkedAudioProcessor, websocket: WebSocket | None = None
    ) -> tuple[np.ndarray, int]:
        from . import stream_chunk_ops
        return await stream_chunk_ops.process_chunk_only(self, chunk_index, processor, websocket)

    async def _stream_processed_chunk(
        self, pcm_samples: np.ndarray, chunk_index: int, processor: ChunkedAudioProcessor, websocket: WebSocket
    ) -> None:
        from . import stream_chunk_ops
        await stream_chunk_ops.stream_processed_chunk(self, pcm_samples, chunk_index, processor, websocket)

    async def _process_and_stream_chunk(
        self,
        chunk_index: int,
        processor: ChunkedAudioProcessor,
        websocket: WebSocket,
        on_progress: Callable[[int, float, str], Any] | None = None,
    ) -> None:
        from . import stream_chunk_ops
        await stream_chunk_ops.process_and_stream_chunk(self, chunk_index, processor, websocket, on_progress)

    def _apply_boundary_crossfade(
        self, prev_tail: np.ndarray, current_chunk: np.ndarray, crossfade_samples: int
    ) -> np.ndarray:
        from . import stream_chunk_ops
        return stream_chunk_ops.apply_boundary_crossfade(prev_tail, current_chunk, crossfade_samples)

    async def _prefetch_next_track(self, current_track_id: int, preset: str, intensity: float) -> None:
        from . import stream_prefetch
        await stream_prefetch.prefetch_next_track(self, current_track_id, preset, intensity)


    async def stream_enhanced_audio(
        self,
        track_id: int,
        preset: str,
        intensity: float,
        websocket: WebSocket,
        on_progress: Callable[[int, float, str], Any] | None = None
    ) -> None:
        """Stream enhanced (mastered) audio chunks. See stream_enhanced.py."""
        from . import stream_enhanced
        await stream_enhanced.stream_enhanced_audio(
            self, track_id, preset, intensity, websocket, on_progress
        )

    async def stream_normal_audio(
        self,
        track_id: int,
        websocket: WebSocket,
        start_position: float = 0.0,
        on_progress: Callable[[int, float, str], Any] | None = None
    ) -> None:
        """Stream original (unprocessed) audio chunks. See stream_normal.py."""
        from . import stream_normal
        await stream_normal.stream_normal_audio(
            self, track_id, websocket, start_position, on_progress
        )

    async def stream_enhanced_audio_from_position(
        self,
        track_id: int,
        preset: str,
        intensity: float,
        websocket: WebSocket,
        start_position: float,
        on_progress: Callable[[int, float, str], Any] | None = None
    ) -> None:
        """Stream enhanced audio starting from a seek position. See stream_seek.py."""
        from . import stream_seek
        await stream_seek.stream_enhanced_audio_from_position(
            self, track_id, preset, intensity, websocket, start_position, on_progress
        )
