#!/usr/bin/env python3

"""
Normal-stream per-chunk pump
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The read/send loop of :func:`stream_normal.stream_normal_audio`, extracted so
the handler is the semaphore/cancellation skeleton and this is the work it
supervises (#5032).

The split point is deliberate. #5032's own proposed fix says to leave the
semaphore/cancel/finally skeleton in the handler, because that is where the
#3493/#4999/#5074 fix history lives — so the permit, the cancel event and the
temp-WAV cleanup all stay there, and only the loop between them moves. What
that buys is a unit boundary: chunk-production and delivery can now be read,
changed and reasoned about without the 200 lines of setup and teardown around
them.

The look-ahead task is owned end-to-end here rather than by the caller. It is
created, awaited and drained inside this function's own try/finally, so #3493's
guarantee — no in-flight read task survives the loop, however the loop exits —
holds without the handler needing a second drain in its own finally.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable

import numpy as np
import soundfile as sf
from fastapi import WebSocket

from . import audio_stream_controller as _asc
from .executors import run_in_stream_executor

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


@dataclass
class ChunkPumpResult:
    """What the loop delivered, for the caller's completion message.

    These three values are exactly what ``send_stream_completion`` needs to
    pick ``reason=stopped/errored/completed`` (#4790).
    """

    stopped_early: bool = False
    failed_chunks: list[int] = field(default_factory=list)
    delivered_samples: int = 0


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
    stopped_early = False
    failed_chunks: list[int] = []
    delivered_samples = 0
    # Consecutive per-chunk read timeouts; reset by any chunk that gets through.
    read_timeouts = 0
    lookahead_read: asyncio.Task[np.ndarray] | None = None

    try:
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

        # Look-ahead variant: short-circuits the disk read if the client
        # vanished during the previous chunk's send (#3874). Runs in a
        # worker thread concurrently with send_pcm_chunk; mirrors the
        # enhanced-path ConnectionError guard in process_chunk_only.
        def _read_audio_chunk_lookahead(filepath: str, start: int, frames: int) -> np.ndarray:
            if not controller._is_websocket_connected(websocket):
                raise ConnectionError("WebSocket disconnected before look-ahead read")
            return _read_audio_chunk(filepath, start, frames)

        # Stream chunks with look-ahead: read chunk N+1 from disk while
        # streaming chunk N to eliminate I/O gaps.
        for chunk_idx in range(start_chunk, total_chunks):
            # Honour pause/resume events from the WebSocket handler (#2106).
            from routers.system import _stream_pause_events, _stream_flow_events
            pause_evt = _stream_pause_events.get(_asc.ws_id(websocket))
            if pause_evt is not None:
                await pause_evt.wait()
            # Honour flow control: wait if frontend buffer is full.
            flow_evt = _stream_flow_events.get(_asc.ws_id(websocket))
            if flow_evt is not None:
                await flow_evt.wait()

            if not controller._is_websocket_connected(websocket):
                logger.info(f"WebSocket disconnected, stopping stream")
                await controller._drain_cancelled_task(lookahead_read)
                lookahead_read = None
                stopped_early = True
                break

            try:
                # Get chunk audio: from look-ahead task or read now
                if lookahead_read is not None:
                    try:
                        # Bounded like every sibling path's chunk producer
                        # (#5082) — see the inline read below for why.
                        # Timed here rather than at create_task() time: the
                        # pause/flow-control waits above sit between the two,
                        # so a legitimately long client pause would otherwise
                        # burn the budget and time out a healthy read.
                        chunk_audio = await asyncio.wait_for(
                            lookahead_read, timeout=_asc.CHUNK_PROCESS_TIMEOUT
                        )
                    except ConnectionError:
                        # Client disconnected during the look-ahead read (#3874).
                        # Clean exit — not a chunk failure, so don't log it as one.
                        stopped_early = True
                        break
                    except TimeoutError:
                        logger.error(
                            f"Look-ahead read for chunk {chunk_idx} timed out after "
                            f"{_asc.CHUNK_PROCESS_TIMEOUT}s (track {track_id})"
                        )
                        read_timeouts += 1
                        raise
                    finally:
                        # wait_for already cancelled the task on timeout, and
                        # the recovery branch drains it; either way this slot
                        # must not be re-awaited next iteration.
                        lookahead_read = None
                else:
                    # #4560: on the first chunk of a seek, start the read at the
                    # requested position rather than at the chunk boundary, and
                    # shorten it to match so the NEXT chunk still begins on its
                    # boundary. Only this branch needs it — the look-ahead below
                    # always reads a full chunk at a boundary, and it is only
                    # ever primed after this first read.
                    trim = first_chunk_trim_samples if chunk_idx == start_chunk else 0
                    start_sample = chunk_idx * interval_samples + trim
                    # Bound the disk read the same way every sibling chunk
                    # producer bounds its worker-thread call (#5082;
                    # stream_chunk_ops/stream_enhanced/stream_seek all use
                    # CHUNK_PROCESS_TIMEOUT). sf.SoundFile open/seek/read on a
                    # stalled network mount or a yanked external drive neither
                    # returns nor raises, so without this the stream hangs
                    # forever holding a MAX_CONCURRENT_STREAMS permit.
                    # TimeoutError is an Exception subclass, so it falls into
                    # the skip-failed-chunk recovery branch below.
                    try:
                        chunk_audio = await asyncio.wait_for(
                            run_in_stream_executor(
                                _read_audio_chunk,
                                streaming_filepath,
                                start_sample,
                                chunk_samples - trim,
                            ),
                            timeout=_asc.CHUNK_PROCESS_TIMEOUT,
                        )
                    except TimeoutError:
                        logger.error(
                            f"Disk read for chunk {chunk_idx} timed out after "
                            f"{_asc.CHUNK_PROCESS_TIMEOUT}s (track {track_id})"
                        )
                        read_timeouts += 1
                        raise

                # Start look-ahead: read next chunk while we stream current one
                if chunk_idx + 1 < total_chunks:
                    next_start = (chunk_idx + 1) * interval_samples
                    lookahead_read = asyncio.create_task(
                        run_in_stream_executor(
                            _read_audio_chunk_lookahead, streaming_filepath, next_start, chunk_samples
                        )
                    )

                # Stream the chunk
                delivered = await controller._send_pcm_chunk(
                    websocket,
                    pcm_samples=chunk_audio,
                    chunk_index=chunk_idx,
                    total_chunks=total_chunks,
                )
                if not delivered:
                    await controller._drain_cancelled_task(lookahead_read)
                    lookahead_read = None
                    await controller._send_error(
                        websocket,
                        track_id,
                        f"Failed to send audio chunk {chunk_idx}",
                        recovery_position=(
                            start_position
                            if chunk_idx == start_chunk
                            else float(chunk_idx * chunk_duration)
                        ),
                    )
                    stopped_early = True
                    break
                delivered_samples += int(chunk_audio.shape[0])
                # A chunk got through, so the storage is responding — only a
                # *run* of timeouts means the backing file is unreachable (#5082).
                read_timeouts = 0

                # Progress update
                if on_progress:
                    progress = ((chunk_idx + 1) / total_chunks) * 100
                    await on_progress(track_id, progress, f"Streamed chunk {chunk_idx + 1}")

            except Exception as chunk_error:
                # Drain the cancelled look-ahead so the next iteration
                # doesn't trip on its CancelledError (#3493).
                await controller._drain_cancelled_task(lookahead_read)
                lookahead_read = None
                logger.error(f"Failed to stream chunk {chunk_idx}: {chunk_error}", exc_info=True)
                # Recovery position: start of the failed chunk (issue #2085)
                normal_recovery_position: float = chunk_idx * chunk_duration
                await controller._send_error(
                    websocket,
                    track_id,
                    f"Failed to stream audio chunk {chunk_idx}",
                    recovery_position=normal_recovery_position,
                )
                # Skip failed chunk and continue with remaining chunks (#3190).
                # Recorded so the terminal message doesn't claim
                # reason="completed" over a stream with gaps (#4790).
                failed_chunks.append(chunk_idx)
                # ...unless the storage itself is gone (#5082): continuing then
                # just strands another executor thread per chunk and delays the
                # permit release by CHUNK_PROCESS_TIMEOUT each time. Stop and
                # let the client retry.
                if read_timeouts >= MAX_CONSECUTIVE_READ_TIMEOUTS:
                    logger.error(
                        f"Normal audio stream aborting: {read_timeouts} consecutive disk-read "
                        f"timeouts (track {track_id}, chunk {chunk_idx}) — backing file "
                        f"{streaming_filepath} appears unreachable"
                    )
                    # Deliberately NOT stopped_early: that reports
                    # reason="stopped", which #4790 reserves for a clean
                    # client-driven exit. failed_chunks is non-empty here, so
                    # falling out of the loop lands on the reason="errored"
                    # branch — the accurate one for a server-side abort.
                    break
                continue

    finally:
        # Drain any in-flight look-ahead read task (#3493). Owned here rather
        # than in the handler's finally: the task cannot outlive this function,
        # so this is the narrowest scope that still covers every exit path.
        await controller._drain_cancelled_task(lookahead_read)

    return ChunkPumpResult(
        stopped_early=stopped_early,
        failed_chunks=failed_chunks,
        delivered_samples=delivered_samples,
    )
