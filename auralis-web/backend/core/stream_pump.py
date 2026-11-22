#!/usr/bin/env python3

"""
Shared chunk-pump loop
~~~~~~~~~~~~~~~~~~~~~~

The look-ahead / gate / drain / send loop the normal pump (stream_normal_chunks.py) and the
enhanced/seek pump (stream_enhanced_chunks.py) both run (#6627). They were two copies that each cited
the same fix lineage (#3493, #3874, #4790, #5082), so a fix to the loop had to land twice.

What differs is a :class:`ChunkPumpFlavour`: how a chunk is produced (a disk read, or DSP), how it is
sent, the recovery position a failed send reports, an optional mid-stream stop check (enhancement
toggled off, #2866), and what a failed chunk does to the stream. The normal flavour counts consecutive
read timeouts (#5082); the enhanced one ends on a DSP timeout (#4999) and treats ConnectionError as a
clean client exit. Each flavour's chunk-error hook decides, so those rules stay where they were made.

The look-ahead task is owned end-to-end here: created, awaited and drained inside this function's own
try/finally, so no in-flight task survives the loop however it exits (#3493).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

import numpy as np
from fastapi import WebSocket

from .stream_gates import wait_for_stream_gates
from .stream_lifecycle import ChunkPumpResult

if TYPE_CHECKING:
    from .audio_stream_controller import AudioStreamController

logger = logging.getLogger(__name__)


class ChunkPumpFlavour(ABC):
    """What one stream type supplies to :func:`run_chunk_pump`."""

    #: Names the stream in log lines.
    label: str
    #: Extra ``_send_error`` kwargs on every error this stream sends (the enhanced ``error_code``).
    error_kwargs: dict[str, Any]

    def should_stop(self) -> bool:
        """True to end the stream cleanly before the next chunk (checked ahead of the gates)."""
        return False

    @abstractmethod
    async def produce(self, chunk_idx: int) -> np.ndarray | None:
        """Produce *chunk_idx* now (no look-ahead armed); None if the client is gone."""

    @abstractmethod
    def lookahead(self, chunk_idx: int) -> Coroutine[Any, Any, Any]:
        """The coroutine that produces *chunk_idx* while the previous one is being sent."""

    @abstractmethod
    async def take_lookahead(self, task: 'asyncio.Task[Any]', chunk_idx: int) -> np.ndarray | None:
        """Await the armed look-ahead for *chunk_idx*; None if the client disconnected (#3874)."""

    @abstractmethod
    async def send(self, chunk: np.ndarray, chunk_idx: int) -> bool:
        """Send *chunk*; False when it was not delivered."""

    @abstractmethod
    def recovery_position(self, chunk_idx: int) -> float:
        """Where the client may resume when *chunk_idx* could not be sent (#2085)."""

    async def on_delivered(self, chunk_idx: int) -> None:
        """Called after *chunk_idx* was delivered (progress, counters)."""

    @abstractmethod
    async def on_chunk_error(self, exc: Exception, chunk_idx: int, result: ChunkPumpResult) -> bool:
        """Handle *chunk_idx* failing with *exc* (the look-ahead is already drained).

        Returns True to go on with the next chunk, False to end the stream. A flavour records a
        server-side abort in ``result.failed_chunks`` and a clean client exit as ``stopped_early``:
        the end frame reports "errored" for the one and "stopped" for the other (#4790, #5995).
        """


async def run_chunk_pump(
    controller: 'AudioStreamController',
    websocket: WebSocket,
    flavour: ChunkPumpFlavour,
    *,
    track_id: int,
    start_chunk: int,
    total_chunks: int,
) -> ChunkPumpResult:
    """Produce and send every chunk from *start_chunk*, producing chunk N+1 while N is sent."""
    result = ChunkPumpResult()
    lookahead: asyncio.Task[Any] | None = None

    try:
        for chunk_idx in range(start_chunk, total_chunks):
            if flavour.should_stop():
                result.stopped_early = True
                break

            # Honour pause/resume (#2106) and flow control (frontend buffer full).
            await wait_for_stream_gates(websocket)

            if not controller._is_websocket_connected(websocket):
                logger.info(f"WebSocket disconnected, stopping {flavour.label}")
                result.stopped_early = True
                break

            try:
                if lookahead is not None:
                    # The slot is consumed whatever the outcome, so a failed look-ahead is never
                    # re-awaited next iteration.
                    armed, lookahead = lookahead, None
                    chunk = await flavour.take_lookahead(armed, chunk_idx)
                else:
                    chunk = await flavour.produce(chunk_idx)
                if chunk is None:
                    result.stopped_early = True  # client disconnected during the look-ahead (#3874)
                    break

                if chunk_idx + 1 < total_chunks:
                    lookahead = asyncio.create_task(flavour.lookahead(chunk_idx + 1))

                if not await flavour.send(chunk, chunk_idx):
                    await controller._drain_cancelled_task(lookahead)
                    lookahead = None
                    await controller._send_error(
                        websocket,
                        track_id,
                        f"Failed to send audio chunk {chunk_idx}",
                        recovery_position=flavour.recovery_position(chunk_idx),
                        **flavour.error_kwargs,
                    )
                    result.stopped_early = True
                    break
                result.delivered_samples += int(chunk.shape[0])
                await flavour.on_delivered(chunk_idx)

            except Exception as exc:
                # Drain the look-ahead so its CancelledError cannot escape the next iteration's
                # await and kill the stream (#3493).
                await controller._drain_cancelled_task(lookahead)
                lookahead = None
                if not await flavour.on_chunk_error(exc, chunk_idx, result):
                    break

    finally:
        # The narrowest scope that covers every exit path (#3493).
        await controller._drain_cancelled_task(lookahead)

    return result
