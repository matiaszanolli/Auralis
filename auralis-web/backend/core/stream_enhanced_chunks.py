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

The look-ahead task is owned end-to-end here. It is created, awaited and
drained inside this function's own try/finally, so #3493's guarantee — no
in-flight processing task survives the loop, however the loop exits — holds
without the handler needing a second drain.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any, NamedTuple
from collections.abc import Callable

from fastapi import WebSocket

from . import audio_stream_controller as _asc
from .chunk_boundaries import emitted_chunk_start
from .stream_gates import wait_for_stream_gates
from .stream_messages import ChunkPumpResult

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
    stopped_early = False
    failed_chunks: list[int] = []
    delivered_samples = 0
    lookahead_task: asyncio.Task[Any] | None = None

    try:
        for chunk_idx in range(start_chunk_idx, processor.total_chunks):
            # Stop streaming if enhancement was toggled off mid-stream (fixes #2866).
            if controller._get_enhancement_enabled and not controller._get_enhancement_enabled():
                logger.info(
                    f"Enhancement disabled mid-stream, stopping {label} for track {track_id}"
                )
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                stopped_early = True
                break

            # Honour pause/resume (#2106) and flow control (frontend buffer full).
            await wait_for_stream_gates(websocket)

            if not controller._is_websocket_connected(websocket):
                logger.info(f"WebSocket disconnected, stopping {label}")
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
                        # Client disconnected during look-ahead processing
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
                    await controller._send_error(
                        websocket,
                        track_id,
                        f"Failed to send audio chunk {chunk_idx}",
                        recovery_position=_recovery_position(
                            chunk_idx, start_chunk_idx, effective_position
                        ),
                        error_code=error_code,
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

                # Pre-fetch was disabled in #3513 / BE-NEW-55: it populated a
                # per-stream cache (system.py creates one fresh per
                # play_enhanced) that nothing else reads. Re-enable once the
                # cache manager is hoisted to a process-wide singleton.

            except ConnectionError:
                # Client disconnected — clean exit
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
                # end the stream rather than continuing to reuse it.
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                logger.error(
                    f"Chunk {chunk_idx} DSP timed out for track {track_id}; "
                    f"ending {label} rather than reusing a processor an "
                    f"orphaned thread may still be running inside"
                )
                await controller._send_error(
                    websocket,
                    track_id,
                    f"Audio processing timed out on chunk {chunk_idx}; stream stopped",
                    recovery_position=_recovery_position(
                        chunk_idx, start_chunk_idx, effective_position
                    ),
                    error_code=error_code,
                )
                stopped_early = True
                break

            except Exception as chunk_error:
                # Cancel look-ahead task on error AND drain it so the
                # CancelledError that would otherwise be raised by the
                # next iteration's `await lookahead_task` doesn't escape
                # `except Exception` and kill the stream (fixes #3493 /
                # the #3190 recovery loop).
                await controller._drain_cancelled_task(lookahead_task)
                lookahead_task = None
                logger.error(
                    f"Failed to process chunk {chunk_idx}: {chunk_error}",
                    exc_info=True
                )
                await controller._send_error(
                    websocket,
                    track_id,
                    f"Failed to process audio chunk {chunk_idx}",
                    recovery_position=_recovery_position(
                        chunk_idx, start_chunk_idx, effective_position
                    ),
                    error_code=error_code,
                )
                # Skip failed chunk and continue with remaining chunks (#3190).
                # Recorded so the terminal message doesn't claim reason="completed"
                # over a stream with gaps (#4790).
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
