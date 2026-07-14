#!/usr/bin/env python3

"""
Stream Chunk Operations
~~~~~~~~~~~~~~~~~~~~~~~

Per-chunk processing/streaming helpers shared by the enhanced and seek
streaming entry points (stream_enhanced.py, stream_seek.py). Not used by
the normal (unprocessed) streaming path, which reads chunks directly from
disk without DSP or crossfade.

Extracted from audio_stream_controller.py (#4071). Functions take the
AudioStreamController instance as `controller` since they read/write
controller.cache_manager, controller._chunk_tails, etc.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

import numpy as np
from fastapi import WebSocket

from . import audio_stream_controller as _asc
from .chunk_cache import SimpleChunkCache

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
    Process a single chunk (cache check + DSP) without streaming.

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

    # Try to get from cache first
    pcm_samples: np.ndarray | None = None
    sr: int | None = None

    try:
        if isinstance(controller.cache_manager, SimpleChunkCache):
            cached_result: tuple[np.ndarray, int] | None = controller.cache_manager.get(
                track_id=processor.track_id,
                chunk_idx=chunk_index,
                preset=processor.preset,
                intensity=processor.intensity,
                # #4358: key on the file signature so an in-session file change
                # (same track_id) misses instead of serving stale audio.
                file_signature=processor.file_signature,
            )
            if cached_result:
                pcm_samples, sr = cached_result
                logger.info(f"Cache HIT: chunk {chunk_index}, preset {processor.preset}")
                # #3832: record the cached chunk's level so the LevelManager
                # history stays chronologically consistent — otherwise a
                # later cache-MISS chunk smooths against the wrong previous
                # RMS. Best-effort: state-sync only, never fails the stream.
                note_level = getattr(processor, "note_cached_chunk_level", None)
                if note_level is not None:
                    try:
                        await asyncio.to_thread(note_level, pcm_samples, chunk_index)
                    except Exception as e:
                        logger.debug(f"Cache-hit level recording skipped (not critical): {e}")
    except Exception as e:
        logger.debug(f"Cache lookup failed (not critical): {e}")

    # Process chunk if not cached
    if pcm_samples is None:
        # Guard: don't waste CPU on DSP if the client disconnected (fixes #2076)
        if websocket is not None and not controller._is_websocket_connected(websocket):
            raise ConnectionError(f"WebSocket disconnected before processing chunk {chunk_index}")
        logger.debug(f"Cache MISS: Processing chunk {chunk_index}")
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
            raise TimeoutError(
                f"Chunk {chunk_index} processing timed out after {_asc.CHUNK_PROCESS_TIMEOUT}s"
            ) from e
        sr = processor.sample_rate

        logger.debug(
            f"Chunk {chunk_index}: processed {len(pcm_samples)} samples at {sr}Hz"
        )

        # Store in cache for future use
        try:
            if isinstance(controller.cache_manager, SimpleChunkCache) and sr is not None:
                controller.cache_manager.put(
                    track_id=processor.track_id,
                    chunk_idx=chunk_index,
                    preset=processor.preset,
                    intensity=processor.intensity,
                    audio=pcm_samples,
                    sample_rate=sr,
                    file_signature=processor.file_signature,  # #4358
                )
        except Exception as e:
            logger.debug(f"Failed to cache chunk (not critical): {e}")

    assert pcm_samples is not None
    assert sr is not None
    return pcm_samples, sr


def apply_boundary_crossfade(
    prev_tail: np.ndarray, current_chunk: np.ndarray, crossfade_samples: int
) -> np.ndarray:
    """No-op boundary handler (fixes #3514 / BE-NEW-56).

    The previous version of this function applied a sin²(0 -> pi/2) fade-in
    to the first 200 ms of every non-first chunk, but did NOT mix the
    previous tail (commit 48a038ee removed the mix to avoid pre-echo
    per #3186). Because adjacent chunks are emitted non-overlapping in
    time, the bare fade-in produced an audible 200 ms volume dip at
    every 10 s boundary — a periodic 'breathing' artefact most evident
    on dense full-band content.

    ChunkOperations renders each chunk WITH 5 s of context on each side
    (chunk_operations.py trim_context), so the DSP state — compressor
    envelope, EQ filters, etc. — is already continuous across the
    boundary. We can safely emit the unmixed chunk; no boundary fade is
    needed. Kept as a no-op (rather than removing the call) so the
    `prev_tail` storage in _chunk_tails_lock remains available if a
    future variant needs it again.

    Args:
        prev_tail: Last N samples from previous chunk (unused).
        current_chunk: Current chunk audio.
        crossfade_samples: Number of samples that *would* have been
            crossfaded (unused).

    Returns:
        current_chunk unchanged.
    """
    _ = prev_tail, crossfade_samples  # explicitly unused
    return current_chunk


async def stream_processed_chunk(
    controller: 'AudioStreamController',
    pcm_samples: np.ndarray,
    chunk_index: int,
    processor: 'ChunkedAudioProcessor',
    websocket: WebSocket,
) -> None:
    """
    Apply crossfade and stream already-processed PCM samples to client.

    Args:
        controller: AudioStreamController instance
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
    async with controller._chunk_tails_lock:
        if chunk_index > 0 and processor.track_id in controller._chunk_tails:
            prev_tail = controller._chunk_tails[processor.track_id]
            pcm_samples = controller._apply_boundary_crossfade(
                prev_tail, pcm_samples, crossfade_samples
            )
            logger.debug(
                f"Applied {crossfade_duration_ms}ms crossfade between chunks "
                f"{chunk_index-1} and {chunk_index}"
            )

        # Store tail for next chunk (last N samples) if not the last chunk
        if chunk_index < processor.total_chunks - 1:
            tail_samples = min(crossfade_samples, len(pcm_samples))
            controller._chunk_tails[processor.track_id] = pcm_samples[-tail_samples:].copy()
        else:
            # Last chunk - clean up tail storage
            controller._chunk_tails.pop(processor.track_id, None)

    # Server already applied the boundary crossfade above; send 0 so the
    # client does not double-apply it (fixes #2188: double crossfade).
    await controller._send_pcm_chunk(
        websocket,
        pcm_samples=pcm_samples,
        chunk_index=chunk_index,
        total_chunks=processor.total_chunks,
        crossfade_samples=0,
    )


async def process_and_stream_chunk(
    controller: 'AudioStreamController',
    chunk_index: int,
    processor: 'ChunkedAudioProcessor',
    websocket: WebSocket,
    on_progress: Callable[[int, float, str], Any] | None = None,
) -> None:
    """Process single chunk and stream PCM samples to client (legacy entry point)."""
    pcm_samples, _sr = await controller._process_chunk_only(chunk_index, processor, websocket)
    await controller._stream_processed_chunk(pcm_samples, chunk_index, processor, websocket)


async def drop_chunk_tail(controller: 'AudioStreamController', track_id: int) -> None:
    """Pop a track's chunk tail under _chunk_tails_lock.

    Five sites pop from controller._chunk_tails (failure-recovery, two
    end-of-stream finally blocks, the prefetch path, and the seek-path
    finally). Only stream_processed_chunk's read/write was protected
    by _chunk_tails_lock — the others were lock-free, undermining the
    lock's stated rationale (#2326: 'serialise read-check-write so
    concurrent seeks cannot produce a torn tail'). Fixes #3527 /
    BE-NEW-69 by routing all pops through this helper.
    """
    async with controller._chunk_tails_lock:
        controller._chunk_tails.pop(track_id, None)


async def drain_cancelled_task(task: asyncio.Task[Any] | None) -> None:
    """Cancel a task (if still running) and wait for it to actually exit,
    suppressing CancelledError and any teardown exceptions.

    Fixes #3493: prior code did `task.cancel()` and then on the next loop
    iteration `await task` would raise CancelledError (a BaseException —
    not caught by `except Exception`), tearing down the entire stream
    instead of skipping the failed chunk as #3190 intended. Also closes
    the look-ahead-orphan leak on outer-block exit.
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
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task

