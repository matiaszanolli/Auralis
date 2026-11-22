#!/usr/bin/env python3

"""
Normal-stream per-chunk pump
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The read/send work of :func:`stream_normal.stream_normal_audio` (#5032), as
the normal flavour of the shared loop in stream_pump.py (#6627): chunks are
read from disk, the first one trimmed to a seek target (#4560), and a run of
read timeouts ends the stream (#5082). The handler keeps the permit, the
cancel event and the temp-WAV cleanup.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import numpy as np
from fastapi import WebSocket

from . import audio_stream_controller as _asc
from .executors import run_in_stream_executor
from .stream_lifecycle import ChunkPumpResult
from .stream_pump import ChunkPumpFlavour, run_chunk_pump
from .stream_normal_reads import (
    ReadTimeout,
    await_lookahead_read,
    read_audio_chunk,
    read_chunk_now,
)

logger = logging.getLogger(__name__)

# How many consecutive per-chunk disk-read timeouts end the stream (#5082).
# Bounding each read with wait_for stops the stream hanging forever, but it
# does NOT stop the blocking sf.SoundFile read underneath: wait_for bounds the
# *coroutine*, and the worker thread it abandons keeps running in the default
# executor — the orphaned-thread caveat #4815/#4727 record. This fix does not
# eliminate that leak. So on storage that is genuinely gone, retrying every
# chunk would strand one executor thread per chunk and hold the stream permit
# for total_chunks x CHUNK_PROCESS_TIMEOUT. Two in a row is enough evidence
# that the backing file is unreachable rather than one chunk being slow.
MAX_CONSECUTIVE_READ_TIMEOUTS: int = 2


class _NormalFlavour(ChunkPumpFlavour):
    """Disk reads with look-ahead I/O; no DSP."""

    label = "normal stream"

    def __init__(
        self,
        controller: '_asc.AudioStreamController',
        websocket: WebSocket,
        *,
        track_id: int,
        streaming_filepath: str,
        start_chunk: int,
        total_chunks: int,
        interval_samples: int,
        chunk_samples: int,
        first_chunk_trim_samples: int,
        chunk_duration: float,
        start_position: float,
        on_progress: Callable[[int, float, str], Any] | None,
    ) -> None:
        self.controller = controller
        self.websocket = websocket
        self.track_id = track_id
        self.filepath = streaming_filepath
        self.start_chunk = start_chunk
        self.total_chunks = total_chunks
        self.interval_samples = interval_samples
        self.chunk_samples = chunk_samples
        self.first_chunk_trim_samples = first_chunk_trim_samples
        self.chunk_duration = chunk_duration
        self.start_position = start_position
        self.on_progress = on_progress
        self.error_kwargs: dict[str, Any] = {}
        # Consecutive per-chunk read timeouts; reset by any chunk that gets through.
        self.read_timeouts = 0

    async def produce(self, chunk_idx: int) -> np.ndarray | None:
        # #4560: on the first chunk of a seek, start the read at the requested position rather than
        # at the chunk boundary, and shorten it to match so the NEXT chunk still begins on its
        # boundary. The look-ahead always reads a full chunk at a boundary, and is only ever primed
        # after this first read.
        trim = self.first_chunk_trim_samples if chunk_idx == self.start_chunk else 0
        return await read_chunk_now(
            self.filepath,
            chunk_idx,
            chunk_idx * self.interval_samples + trim,
            self.chunk_samples - trim,
            self.track_id,
        )

    def _read_lookahead(self, filepath: str, start: int, frames: int) -> np.ndarray:
        # Short-circuits the disk read if the client vanished during the previous chunk's send
        # (#3874); runs in a worker thread concurrently with the send.
        if not self.controller._is_websocket_connected(self.websocket):
            raise ConnectionError("WebSocket disconnected before look-ahead read")
        return read_audio_chunk(filepath, start, frames)

    def lookahead(self, chunk_idx: int) -> Coroutine[Any, Any, np.ndarray]:
        return run_in_stream_executor(
            self._read_lookahead, self.filepath, chunk_idx * self.interval_samples, self.chunk_samples
        )

    async def take_lookahead(self, task: 'asyncio.Task[Any]', chunk_idx: int) -> np.ndarray | None:
        return await await_lookahead_read(task, chunk_idx, self.track_id)

    async def send(self, chunk: np.ndarray, chunk_idx: int) -> bool:
        return await self.controller._send_pcm_chunk(
            self.websocket, pcm_samples=chunk, chunk_index=chunk_idx, total_chunks=self.total_chunks
        )

    def recovery_position(self, chunk_idx: int) -> float:
        if chunk_idx == self.start_chunk:
            return self.start_position
        return float(chunk_idx * self.chunk_duration)

    async def on_delivered(self, chunk_idx: int) -> None:
        # A chunk got through, so the storage is responding: only a *run* of timeouts means the
        # backing file is unreachable (#5082).
        self.read_timeouts = 0
        if self.on_progress:
            progress = ((chunk_idx + 1) / self.total_chunks) * 100
            await self.on_progress(self.track_id, progress, f"Streamed chunk {chunk_idx + 1}")

    async def on_chunk_error(self, exc: Exception, chunk_idx: int, result: ChunkPumpResult) -> bool:
        if isinstance(exc, ReadTimeout):
            self.read_timeouts += 1
        logger.error(f"Failed to stream chunk {chunk_idx}: {exc}", exc_info=exc)
        aborting = self.read_timeouts >= MAX_CONSECUTIVE_READ_TIMEOUTS
        await self.controller._send_error(
            self.websocket,
            self.track_id,
            f"Failed to stream audio chunk {chunk_idx}",
            # Start of the failed chunk (#2085).
            recovery_position=chunk_idx * self.chunk_duration,
            stream_continues=not aborting,  # False on the read-timeout abort, which ends the stream (#5867)
        )
        # Skip the failed chunk and continue (#3190), recorded so the end frame does not claim
        # reason="completed" over a stream with gaps (#4790)...
        result.failed_chunks.append(chunk_idx)
        if not aborting:
            return True
        # ...unless the storage itself is gone (#5082): continuing would strand another executor
        # thread per chunk and hold the permit CHUNK_PROCESS_TIMEOUT longer each time. Not
        # stopped_early, which reports reason="stopped" for a clean client exit (#4790); the
        # non-empty failed_chunks reports "errored", accurate for a server-side abort.
        logger.error(
            f"Normal audio stream aborting: {self.read_timeouts} consecutive disk-read "
            f"timeouts (track {self.track_id}, chunk {chunk_idx}) — backing file "
            f"{self.filepath} appears unreachable"
        )
        return False


async def pump_normal_chunks(
    controller: '_asc.AudioStreamController',
    websocket: WebSocket,
    *,
    track_id: int,
    streaming_filepath: str,
    start_chunk: int,
    total_chunks: int,
    interval_samples: int,
    chunk_samples: int,
    first_chunk_trim_samples: int,
    chunk_duration: float,
    start_position: float,
    on_progress: Callable[[int, float, str], Any] | None = None,
) -> ChunkPumpResult:
    """Read and send every chunk from *start_chunk*, with look-ahead I/O.

    Returns what was delivered; raising is reserved for failures the handler's
    own except-clauses are responsible for (a client disconnect, or an error
    outside a single chunk's scope).
    """
    flavour = _NormalFlavour(
        controller,
        websocket,
        track_id=track_id,
        streaming_filepath=streaming_filepath,
        start_chunk=start_chunk,
        total_chunks=total_chunks,
        interval_samples=interval_samples,
        chunk_samples=chunk_samples,
        first_chunk_trim_samples=first_chunk_trim_samples,
        chunk_duration=chunk_duration,
        start_position=start_position,
        on_progress=on_progress,
    )
    return await run_chunk_pump(
        controller, websocket, flavour,
        track_id=track_id, start_chunk=start_chunk, total_chunks=total_chunks,
    )
