#!/usr/bin/env python3

"""
Stream Chunk Operations
~~~~~~~~~~~~~~~~~~~~~~~

Per-chunk processing/streaming helpers shared by the enhanced and seek
streaming entry points (stream_enhanced.py, stream_seek.py). Not used by
the normal (unprocessed) streaming path, which reads chunks directly from
disk without DSP.

Extracted from audio_stream_controller.py (#4071). Functions take the
AudioStreamController instance as `controller`.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

import numpy as np
from fastapi import WebSocket

from . import audio_stream_controller as _asc
from .chunk_streaming import ChunkCancelledError, invalidate_pooled_processor

if TYPE_CHECKING:
    from .audio_stream_controller import AudioStreamController
    from .chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger(__name__)


async def process_chunk_only(
    controller: 'AudioStreamController',
    chunk_index: int,
    processor: 'ChunkedAudioProcessor',
    websocket: WebSocket | None = None,
) -> tuple[np.ndarray, int]:
    """
    Process a single chunk (the processor's disk-cache check + DSP) without streaming.

    Returns the processed PCM samples and sample rate. Used by the
    look-ahead pipeline so chunk N+1 can be processed while chunk N
    is being streamed.

    Args:
        controller: AudioStreamController instance
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

    # Cache hits are served inside processor.process_chunk_safe() by the
    # on-disk chunk tier, which also restores level history (#5492 removed
    # the in-memory SimpleChunkCache that used to sit in front of it).
    #
    # Guard: don't waste CPU on DSP if the client disconnected (fixes #2076)
    if websocket is not None and not controller._is_websocket_connected(websocket):
        raise ConnectionError(f"WebSocket disconnected before processing chunk {chunk_index}")
    # Bound the per-chunk DSP so a hung thread can't wedge the stream
    # forever (#3852). TimeoutError is an Exception subclass, so it
    # flows into the caller's skip-failed-chunk recovery branch.
    try:
        _chunk_path, pcm_samples = await asyncio.wait_for(
            processor.process_chunk_safe(chunk_index, fast_start=fast_start),
            timeout=_asc.CHUNK_PROCESS_TIMEOUT,
        )
    except TimeoutError as e:
        logger.error(
            f"Chunk {chunk_index} DSP timed out after {_asc.CHUNK_PROCESS_TIMEOUT}s "
            f"(track {processor.track_id}, preset {processor.preset})"
        )
        # #5335: wait_for abandoned the coroutine, not the executor thread,
        # which may still be advancing the pooled HybridProcessor. Drop it
        # from the factory so the next stream or seek of this track builds
        # a fresh one. Best-effort: never mask the timeout itself.
        try:
            invalidate_pooled_processor(
                processor,
                chunk_index,
                f"DSP timed out after {_asc.CHUNK_PROCESS_TIMEOUT}s",
            )
        except Exception as invalidate_error:
            logger.warning(
                f"Could not invalidate the processor after chunk {chunk_index} "
                f"timed out: {invalidate_error}"
            )
        raise TimeoutError(
            f"Chunk {chunk_index} processing timed out after {_asc.CHUNK_PROCESS_TIMEOUT}s"
        ) from e
    except ChunkCancelledError:
        # #4815: the owning stream was cancelled (seek/track-change/
        # disconnect) and chunk_streaming.process_chunk bailed out before
        # starting DSP. In practice the awaiting task has usually already
        # unwound via asyncio.CancelledError by the time this is even
        # reachable — but if it IS reached, this must NOT be logged or
        # retried as a processing failure. Re-raised as ConnectionError so
        # it flows into the callers' existing "client disconnected — clean
        # exit" handling (stream_enhanced.py/stream_seek.py already treat
        # ConnectionError this way; no new except clause needed there).
        logger.debug(f"Chunk {chunk_index} abandoned: stream cancelled")
        raise ConnectionError(
            f"Chunk {chunk_index} abandoned: owning stream was cancelled"
        )
    sr = processor.sample_rate

    logger.debug(
        f"Chunk {chunk_index}: processed {len(pcm_samples)} samples at {sr}Hz"
    )

    assert sr is not None
    return pcm_samples, sr


async def stream_processed_chunk(
    controller: 'AudioStreamController',
    pcm_samples: np.ndarray,
    chunk_index: int,
    processor: 'ChunkedAudioProcessor',
    websocket: WebSocket,
) -> bool:
    """
    Stream already-processed PCM samples to client.

    No boundary crossfade is applied, and none is needed: ChunkOperations
    renders each chunk WITH 5 s of context on each side and then trims it to
    its non-overlapping CHUNK_INTERVAL segment (#3514), so the DSP state —
    compressor envelope, EQ filters — is already continuous across the
    boundary while adjacent chunks share no samples. An earlier version faded
    in the first 200 ms of every non-first chunk without mixing the previous
    tail (#3186), which produced an audible periodic volume dip; it was made a
    no-op in #3514 and removed outright, along with its tail storage and the
    crossfade_samples wire field, in #4642.

    Args:
        controller: AudioStreamController instance
        pcm_samples: Processed PCM audio array
        chunk_index: Index of this chunk
        processor: ChunkedProcessor instance (for metadata)
        websocket: WebSocket connection

    Returns:
        True only when the complete PCM chunk reached the WebSocket.
    """
    if processor.total_chunks is None:
        raise ValueError("Processor metadata missing: total_chunks is None")
    if processor.sample_rate is None:
        raise ValueError("Processor metadata missing: sample_rate is None")

    return await controller._send_pcm_chunk(
        websocket,
        pcm_samples=pcm_samples,
        chunk_index=chunk_index,
        total_chunks=processor.total_chunks,
    )


async def process_and_stream_chunk(
    controller: 'AudioStreamController',
    chunk_index: int,
    processor: 'ChunkedAudioProcessor',
    websocket: WebSocket,
    on_progress: Callable[[int, float, str], Any] | None = None,
) -> bool:
    """Process single chunk and stream PCM samples to client (legacy entry point)."""
    pcm_samples, _sr = await controller._process_chunk_only(chunk_index, processor, websocket)
    return await controller._stream_processed_chunk(
        pcm_samples, chunk_index, processor, websocket
    )


async def drain_cancelled_task(task: asyncio.Task[Any] | None) -> None:
    """Cancel a task (if still running) and wait for it to actually exit,
    suppressing CancelledError and any teardown exceptions.

    Fixes #3493: prior code did `task.cancel()` and then on the next loop
    iteration `await task` would raise CancelledError (a BaseException —
    not caught by `except Exception`), tearing down the entire stream
    instead of skipping the failed chunk as #3190 intended. Also closes
    the look-ahead-orphan leak on outer-block exit.

    A `CancelledError` raised out of `await task` has two possible origins and
    only one of them may be swallowed (#5083):

    - the drained inner task's own cancellation — suppress, as #3493 intends;
    - a cancellation delivered to the *calling* task while it is parked in that
      await — must propagate. `teardown_connection` and `handle_seek` cancel the
      outer streaming task, and this helper runs mid-loop (stream_normal /
      stream_enhanced), not only during teardown. Swallowing that cancellation
      leaves the old stream sending chunks while `handle_seek` blocks on
      `await old_task`, which is the interleaved-frames failure #3806 closed.

    `Task.cancelling()` (3.11+) is what distinguishes them: it is non-zero only
    when a cancellation was requested against the current task itself.
    """
    if task is None:
        return
    if task.done():
        # Already finished — it may have completed with a result, or raised
        # (e.g. the #3874 ConnectionError look-ahead short-circuit). Retrieve
        # any exception so asyncio doesn't log "Task exception was never
        # retrieved" when a top-of-loop break drains it without awaiting.
        # .exception() raises only if the task was cancelled; suppress that.
        with contextlib.suppress(asyncio.CancelledError):
            task.exception()
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        if _caller_is_being_cancelled():
            raise
    except Exception:
        # Teardown errors from the drained task are not the caller's problem.
        pass


def _caller_is_being_cancelled() -> bool:
    """Whether the *current* task has a cancellation of its own pending (#5083).

    Returns False outside a task context, where there is no caller cancellation
    to preserve — that keeps the pre-#5083 suppress-everything behaviour for
    any caller not running inside a Task.
    """
    current = asyncio.current_task()
    return current is not None and current.cancelling() > 0
