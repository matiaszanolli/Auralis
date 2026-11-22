#!/usr/bin/env python3

"""
Enhanced / seek per-chunk pump
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The process/send loop of :func:`stream_enhanced.stream_enhanced_audio` and
:func:`stream_seek.stream_enhanced_audio_from_position`, extracted so each
handler is the semaphore/cancellation skeleton and this is the work it
supervises (#5032).

A seek is the enhanced stream with a non-zero ``start_chunk_idx``, a trim of
the first chunk, and a recovery position for that first chunk that preserves
the user's exact target. It used to be a second copy of this loop, and the
copies drifted: #4999's TimeoutError fix reached the seek loop only as #5074,
the pause gate likewise, and the enhanced copy never sent a
``recovery_position`` on a chunk DSP timeout at all (#5761). There is one loop
now, so a fix lands once.

The split point is deliberate. #5032's own proposed fix says to leave the
semaphore/cancel/finally skeleton in the handler, because that is where the
#3493/#4999/#5074 fix history lives — so the permit, the cancel event and the
processor teardown all stay there, and only the loop between them moves. What
that buys is a unit boundary: chunk production and delivery can now be read
and changed without the setup and teardown wrapped around them.

The loop itself is the shared one in stream_pump.py, which the normal
stream runs too (#6627); this module is the enhanced flavour of it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, NamedTuple

import numpy as np

from fastapi import WebSocket

from . import audio_stream_controller as _asc
from .chunk_boundaries import emitted_chunk_start
from .stream_lifecycle import ChunkPumpResult
from .stream_pump import ChunkPumpFlavour, run_chunk_pump

logger = logging.getLogger(__name__)

class ProcessorMetadata(NamedTuple):
    """The processor attributes the pump and the stream-start message read."""

    total_chunks: int
    sample_rate: int
    channels: int
    duration: float


def validate_processor_metadata(processor: Any) -> ProcessorMetadata:
    """Return *processor*'s metadata, or raise ValueError if any of it is unloaded.

    Raises rather than asserting so the guard survives ``python -O`` and
    PyInstaller builds (#2735). The returned values are non-Optional, so a
    caller that needs them narrowed (the seek handler does arithmetic on
    ``duration``) uses the result instead of re-reading the attributes.
    """
    if processor is None:
        raise ValueError("Audio processor initialization returned None")
    values: dict[str, Any] = {}
    for attr in ProcessorMetadata._fields:
        value = getattr(processor, attr)
        if value is None:
            raise ValueError(f"Processor metadata missing: {attr} is None")
        values[attr] = value
    return ProcessorMetadata(**values)


def _recovery_position(
    chunk_idx: int, start_chunk_idx: int, effective_position: float | None
) -> float:
    """Where a client may resume after *chunk_idx* fails (issue #2085).

    The first chunk of a seek preserves the user's exact target (#3493 /
    BE-NEW-67). Every other chunk uses the EMITTED start (#4557), not
    ``chunk_idx * chunk_interval``: for chunk >= 1 the core start is
    OVERLAP_DURATION earlier than the first sample the chunk actually
    delivers, so resuming there replays 5s of already-heard audio.
    """
    if effective_position is not None and chunk_idx == start_chunk_idx:
        return effective_position
    return emitted_chunk_start(chunk_idx)


class _EnhancedFlavour(ChunkPumpFlavour):
    """DSP with look-ahead processing; a seek trims its first chunk."""

    def __init__(
        self,
        controller: '_asc.AudioStreamController',
        websocket: WebSocket,
        *,
        track_id: int,
        processor: Any,
        start_chunk_idx: int,
        seek_offset: float,
        effective_position: float | None,
        error_code: str,
        label: str,
        on_progress: Callable[[int, float, str], Any] | None,
    ) -> None:
        self.controller = controller
        self.websocket = websocket
        self.track_id = track_id
        self.processor = processor
        self.start_chunk_idx = start_chunk_idx
        self.seek_offset = seek_offset
        self.effective_position = effective_position
        self.label = label
        self.on_progress = on_progress
        self.error_kwargs: dict[str, Any] = {"error_code": error_code}

    def should_stop(self) -> bool:
        # Stop streaming if enhancement was toggled off mid-stream (#2866).
        enabled = self.controller._get_enhancement_enabled
        if enabled and not enabled():
            logger.info(f"Enhancement disabled mid-stream, stopping {self.label} for track {self.track_id}")
            return True
        return False

    async def produce(self, chunk_idx: int) -> np.ndarray | None:
        pcm_samples, _sr = await self.controller._process_chunk_only(chunk_idx, self.processor, self.websocket)
        # Trim the first chunk to the exact seek position. Only ever produced here: the look-ahead
        # is primed after the first chunk.
        if chunk_idx == self.start_chunk_idx and self.seek_offset > 0:
            trim_samples = round(self.seek_offset * self.processor.sample_rate)
            pcm_samples = pcm_samples[trim_samples:]
            logger.debug(
                f"Seek trim: removed {trim_samples} samples ({self.seek_offset:.2f}s) from chunk {chunk_idx}"
            )
        return pcm_samples

    def lookahead(self, chunk_idx: int) -> Coroutine[Any, Any, Any]:
        return self.controller._process_chunk_only(chunk_idx, self.processor, self.websocket)

    async def take_lookahead(self, task: 'asyncio.Task[Any]', chunk_idx: int) -> np.ndarray | None:
        try:
            chunk: tuple[np.ndarray, int] = await task
        except ConnectionError:
            return None
        return chunk[0]

    async def send(self, chunk: np.ndarray, chunk_idx: int) -> bool:
        return await self.controller._stream_processed_chunk(chunk, chunk_idx, self.processor, self.websocket)

    def recovery_position(self, chunk_idx: int) -> float:
        return _recovery_position(chunk_idx, self.start_chunk_idx, self.effective_position)

    async def on_delivered(self, chunk_idx: int) -> None:
        if self.on_progress:
            chunks_remaining = self.processor.total_chunks - self.start_chunk_idx
            chunks_done = chunk_idx - self.start_chunk_idx + 1
            progress = (chunks_done / chunks_remaining) * 100
            await self.on_progress(self.track_id, progress, f"Processed chunk {chunk_idx + 1}")

    async def on_chunk_error(self, exc: Exception, chunk_idx: int, result: ChunkPumpResult) -> bool:
        if isinstance(exc, ConnectionError):
            result.stopped_early = True  # the client disconnected: a clean exit
            return False
        if isinstance(exc, TimeoutError):
            await self._abort_on_dsp_timeout(chunk_idx, result)
            return False
        logger.error(f"Failed to process chunk {chunk_idx}: {exc}", exc_info=exc)
        await self.controller._send_error(
            self.websocket,
            self.track_id,
            f"Failed to process audio chunk {chunk_idx}",
            recovery_position=self.recovery_position(chunk_idx),
            stream_continues=True,
            **self.error_kwargs,
        )
        # Skip the failed chunk and continue (#3190), recorded so the end frame does not claim
        # reason="completed" over a stream with gaps (#4790).
        result.failed_chunks.append(chunk_idx)
        return True

    async def _abort_on_dsp_timeout(self, chunk_idx: int, result: ChunkPumpResult) -> None:
        """End the stream on a chunk DSP timeout instead of skipping the chunk (#4999/#5074).

        asyncio.wait_for gave up on the wrapper future (stream_chunk_ops.CHUNK_PROCESS_TIMEOUT), but
        the OS thread may still be inside processor.process_chunk_safe(), holding the processor's
        RLock for however long the hung DSP call takes. The #3190 skip-and-continue would make the
        next chunk block on that lock, time out in turn, and cascade every remaining chunk into a
        serial pileup; this stream's processor (like #4727's pooled HybridProcessor) must not be
        touched again.
        """
        logger.error(
            f"Chunk {chunk_idx} DSP timed out for track {self.track_id}; "
            f"ending {self.label} rather than reusing a processor an "
            f"orphaned thread may still be running inside"
        )
        await self.controller._send_error(
            self.websocket,
            self.track_id,
            f"Audio processing timed out on chunk {chunk_idx}; stream stopped",
            recovery_position=self.recovery_position(chunk_idx),
            **self.error_kwargs,
        )
        # A server-side abort, not a client-driven stop: a failed chunk, so the end frame says
        # "errored" like the normal pump's read-timeout abort (#4790, #5995).
        result.failed_chunks.append(chunk_idx)


async def pump_chunks(
    controller: '_asc.AudioStreamController',
    websocket: WebSocket,
    *,
    track_id: int,
    processor: Any,
    start_chunk_idx: int = 0,
    seek_offset: float = 0.0,
    effective_position: float | None = None,
    error_code: str = "STREAMING_ERROR",
    label: str = "enhanced stream",
    on_progress: Callable[[int, float, str], Any] | None = None,
) -> ChunkPumpResult:
    """Process and send every chunk from *start_chunk_idx*, with look-ahead DSP.

    ``seek_offset`` seconds are trimmed from the head of the first chunk;
    ``effective_position`` is the position the client was told it is seeking
    to, reported as the recovery position when that first chunk fails. Plain
    enhanced playback leaves all three at their defaults. ``label`` only
    names the stream in log lines.

    Returns what was delivered; raising is reserved for failures the handler's
    own except-clauses are responsible for.
    """
    flavour = _EnhancedFlavour(
        controller,
        websocket,
        track_id=track_id,
        processor=processor,
        start_chunk_idx=start_chunk_idx,
        seek_offset=seek_offset,
        effective_position=effective_position,
        error_code=error_code,
        label=label,
        on_progress=on_progress,
    )
    return await run_chunk_pump(
        controller, websocket, flavour,
        track_id=track_id, start_chunk=start_chunk_idx, total_chunks=processor.total_chunks,
    )
