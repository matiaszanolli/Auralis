#!/usr/bin/env python3

"""
Normal-stream disk reads
~~~~~~~~~~~~~~~~~~~~~~~~

The bounded chunk producers of :func:`stream_normal_chunks.pump_normal_chunks`
(#5032, #5082, #5839): the blocking reader, the immediate read and the await of
the armed look-ahead read, each capped by ``CHUNK_PROCESS_TIMEOUT``. Kept apart
from the pump loop so the loop reads as control flow and the timeout contract
reads as one unit.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging

import numpy as np
import soundfile as sf

from . import audio_stream_controller as _asc
from .executors import run_in_stream_executor

logger = logging.getLogger(__name__)


class ReadTimeout(TimeoutError):
    """A per-chunk disk read exceeded CHUNK_PROCESS_TIMEOUT (#5082).

    A TimeoutError subclass, so it still lands in the pump's skip-failed-chunk
    recovery branch; the subclass only lets that branch count *read* timeouts
    toward MAX_CONSECUTIVE_READ_TIMEOUTS without mistaking some other
    TimeoutError (a send, a progress callback) for a stalled mount.
    """


# Helper: open → seek → read → close for a single chunk (#2121).
# Uses the streaming filepath (temp WAV for compressed formats, original for PCM).
def read_audio_chunk(filepath: str, start: int, frames: int) -> np.ndarray:
    with sf.SoundFile(filepath) as audio_file:
        audio_file.seek(start)
        # always_2d=True: mono returned as (N, 1) matching stereo shape
        # Do NOT use fill_value: send the last chunk at its actual
        # length to avoid appending silence (#2124).
        return np.asarray(audio_file.read(
            frames=frames, dtype='float32', always_2d=True
        ))


async def await_lookahead_read(
    lookahead_read: asyncio.Task[np.ndarray], chunk_idx: int, track_id: int
) -> np.ndarray | None:
    """Await the armed look-ahead read; None if the client disconnected (#3874).

    Bounded like every sibling path's chunk producer (#5082) — see
    :func:`read_chunk_now` for why. Timed here rather than at create_task()
    time: the pause/flow-control waits sit between the two, so a legitimately
    long client pause would otherwise burn the budget and time out a healthy
    read. wait_for cancels the task on timeout, and the pump's recovery branch
    drains it; either way the caller has already emptied its slot so it is not
    re-awaited next iteration.
    """
    try:
        return await asyncio.wait_for(
            lookahead_read, timeout=_asc.CHUNK_PROCESS_TIMEOUT
        )
    except ConnectionError:
        # Client disconnected during the look-ahead read (#3874). Clean exit —
        # not a chunk failure, so don't log it as one.
        return None
    except TimeoutError as e:
        logger.error(
            f"Look-ahead read for chunk {chunk_idx} timed out after "
            f"{_asc.CHUNK_PROCESS_TIMEOUT}s (track {track_id})"
        )
        raise ReadTimeout(str(e)) from e


async def read_chunk_now(
    streaming_filepath: str,
    chunk_idx: int,
    start_sample: int,
    frames: int,
    track_id: int,
) -> np.ndarray:
    """Read one chunk from disk now, bounded by CHUNK_PROCESS_TIMEOUT (#5082).

    Bound the disk read the same way every sibling chunk producer bounds its
    worker-thread call (stream_chunk_ops/stream_enhanced/stream_seek all use
    CHUNK_PROCESS_TIMEOUT). sf.SoundFile open/seek/read on a stalled network
    mount or a yanked external drive neither returns nor raises, so without
    this the stream hangs forever holding a MAX_CONCURRENT_STREAMS permit.
    The timeout is an Exception subclass, so it falls into the pump's
    skip-failed-chunk recovery branch.
    """
    try:
        return await asyncio.wait_for(
            run_in_stream_executor(
                read_audio_chunk,
                streaming_filepath,
                start_sample,
                frames,
            ),
            timeout=_asc.CHUNK_PROCESS_TIMEOUT,
        )
    except TimeoutError as e:
        logger.error(
            f"Disk read for chunk {chunk_idx} timed out after "
            f"{_asc.CHUNK_PROCESS_TIMEOUT}s (track {track_id})"
        )
        raise ReadTimeout(str(e)) from e
