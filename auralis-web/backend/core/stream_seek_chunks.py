#!/usr/bin/env python3

"""
Seek-stream per-chunk pump
~~~~~~~~~~~~~~~~~~~~~~~~~~

The process/send loop of
:func:`stream_seek.stream_enhanced_audio_from_position`, extracted so the
handler is the semaphore/cancellation skeleton and this is the work it
supervises (#5032).

The split point is deliberate. #5032's own proposed fix says to leave the
semaphore/cancel/finally skeleton in the handler, because that is where the
#3493/#4999/#5074 fix history lives — so the permit, the cancel event and the
processor teardown all stay there, and only the loop between them moves. What
that buys is a unit boundary: chunk production and delivery can now be read
and changed without the setup and teardown wrapped around them.

The look-ahead task is owned end-to-end here. It is created, awaited and
drained inside this function's own try/finally, so #3493's guarantee — no
in-flight processing task survives the loop, however the loop exits — holds
without the handler needing a second drain.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable

from fastapi import WebSocket

from . import audio_stream_controller as _asc
from .chunk_boundaries import emitted_chunk_start

logger = logging.getLogger(__name__)


@dataclass
class ChunkPumpResult:
    """What the loop delivered, for the caller's completion message.

    These three values are exactly what ``send_stream_completion`` needs to
    pick ``reason=stopped/errored/completed`` (#4790).
    """

    stopped_early: bool = False
    failed_chunks: list[int] = field(default_factory=list)
    delivered_samples: int = 0


async def pump_seek_chunks(
    controller: '_asc.AudioStreamController',
    websocket: WebSocket,
    *,
    track_id: int,
    processor: Any,
    start_chunk_idx: int,
    seek_offset: float,
    effective_position: float,
    on_progress: Callable[[int, float, str], Any] | None = None,
) -> ChunkPumpResult:
    """Process and send every chunk from *start_chunk_idx*, with look-ahead DSP.

    Returns what was delivered; raising is reserved for failures the handler's
    own except-clauses are responsible for.
    """
    stopped_early = False
    failed_chunks: list[int] = []
    delivered_samples = 0
    lookahead_task: asyncio.Task[Any] | None = None

    try:
        for chunk_idx in range(start_chunk_idx, processor.total_chunks):
            # Stop streaming if enhancement was toggled off mid-stream (fixes #2866).
            if controller._get_enhancement_enabled and not controller._get_enhancement_enabled():
                logger.info(
                    f"Enhancement disabled mid-stream, stopping seek stream for track {track_id}"
                )
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                stopped_early = True
                break

            # Honour pause/resume and flow control events (fixes missing
            # pause check in seek path — pre-existing bug).
            from routers.system import _stream_pause_events, _stream_flow_events
            pause_evt = _stream_pause_events.get(_asc.ws_id(websocket))
            if pause_evt is not None:
                await pause_evt.wait()
            flow_evt = _stream_flow_events.get(_asc.ws_id(websocket))
            if flow_evt is not None:
                await flow_evt.wait()

            if not controller._is_websocket_connected(websocket):
                logger.info(f"WebSocket disconnected, stopping seek stream")
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                stopped_early = True
                break

            try:
                # Get processed chunk: from look-ahead task or process now
                if lookahead_task is not None:
                    try:
                        pcm_samples, _sr = await lookahead_task
                    except ConnectionError:
                        stopped_early = True
                        break
                    lookahead_task = None
                else:
                    pcm_samples, _sr = await controller._process_chunk_only(chunk_idx, processor, websocket)

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
                        controller._process_chunk_only(chunk_idx + 1, processor, websocket)
                    )

                # Stream current chunk
                delivered = await controller._stream_processed_chunk(
                    pcm_samples, chunk_idx, processor, websocket
                )
                if not delivered:
                    await controller._drain_cancelled_task(lookahead_task)
                    lookahead_task = None
                    recovery_position = (
                        effective_position
                        if chunk_idx == start_chunk_idx
                        else emitted_chunk_start(chunk_idx)
                    )
                    await controller._send_error(
                        websocket,
                        track_id,
                        f"Failed to send audio chunk {chunk_idx}",
                        recovery_position=recovery_position,
                        error_code="SEEK_ERROR",
                    )
                    stopped_early = True
                    break
                delivered_samples += int(pcm_samples.shape[0])

                # Progress update
                if on_progress:
                    chunks_remaining = processor.total_chunks - start_chunk_idx
                    chunks_done = chunk_idx - start_chunk_idx + 1
                    progress = (chunks_done / chunks_remaining) * 100
                    await on_progress(track_id, progress, f"Processed chunk {chunk_idx + 1}")

            except ConnectionError:
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                stopped_early = True
                break

            except TimeoutError:
                # #4999/#5074: a chunk DSP timeout (stream_chunk_ops.CHUNK_PROCESS_TIMEOUT)
                # means asyncio.wait_for gave up on the wrapper future, but the
                # underlying OS thread may still be running inside
                # processor.process_chunk_safe() — holding `processor`'s
                # threading.RLock (_processor_lock) for however long the hung
                # DSP call takes, unbounded. Unlike a plain processing error
                # (#3190's skip-and-continue), the #3190 recovery path is unsafe
                # here: the NEXT chunk's process_chunk_safe() call would block
                # trying to acquire that same still-held lock, itself time out
                # 30s later, and so on — cascading every remaining chunk into a
                # serial pileup of timeouts instead of one clean failure.
                # `processor` (this stream's ChunkedAudioProcessor, analogous to
                # #4727's pooled HybridProcessor) must never be touched again —
                # end the stream rather than continuing to reuse it. Lifted from
                # stream_enhanced.py's #4999 fix, which never reached this
                # structurally identical seek-path loop (#5074).
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                logger.error(
                    f"Chunk {chunk_idx} DSP timed out for track {track_id}; "
                    f"ending seek stream rather than reusing a processor an "
                    f"orphaned thread may still be running inside"
                )
                recovery_position = (
                    effective_position
                    if chunk_idx == start_chunk_idx
                    else emitted_chunk_start(chunk_idx)
                )
                await controller._send_error(
                    websocket,
                    track_id,
                    f"Audio processing timed out on chunk {chunk_idx}; stream stopped",
                    recovery_position=recovery_position,
                    error_code="SEEK_ERROR",
                )
                stopped_early = True
                break

            except Exception as chunk_error:
                # Drain the cancelled look-ahead (#3493) so the next
                # iteration doesn't trip on its CancelledError.
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                logger.error(
                    f"Failed to process chunk {chunk_idx}: {chunk_error}",
                    exc_info=True
                )
                # Seek-path recovery preserves the user's exact target
                # for the first chunk; chunk-start otherwise (#3493 / BE-NEW-67).
                # #4557: "chunk start" is the EMITTED start, not
                # chunk_idx * chunk_interval — resuming at the core start would
                # replay OVERLAP_DURATION of already-delivered audio.
                if chunk_idx == start_chunk_idx:
                    recovery_position = effective_position
                else:
                    recovery_position = emitted_chunk_start(chunk_idx)
                await controller._send_error(
                    websocket,
                    track_id,
                    f"Failed to process audio chunk {chunk_idx}",
                    recovery_position=recovery_position,
                    error_code="SEEK_ERROR",
                )
                # Skip failed chunk and continue (#3190). Recorded so the
                # terminal message doesn't claim reason="completed" over a
                # stream with gaps (#4790).
                failed_chunks.append(chunk_idx)
                continue

    finally:
        # Drain any in-flight look-ahead task (#3493). Owned here rather than
        # in the handler's finally: the task cannot outlive this function, so
        # this is the narrowest scope that still covers every exit path.
        await controller._drain_cancelled_task(lookahead_task)

    return ChunkPumpResult(
        stopped_early=stopped_early,
        failed_chunks=failed_chunks,
        delivered_samples=delivered_samples,
    )
