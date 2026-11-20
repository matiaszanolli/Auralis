#!/usr/bin/env python3

"""
Chunk Streaming Entry Points
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The three per-chunk retrieval entry points extracted from
``ChunkedAudioProcessor`` (#4245): ``process_chunk`` (sync, cache-aware),
``process_chunk_safe`` (async, thread-pool-offloaded), and
``get_wav_chunk_path`` (sync, writes straight to the on-disk WAV cache — the
primary path for the unified streaming architecture).

Each function takes the owning ``ChunkedAudioProcessor`` as its first
argument and reads/updates its state directly (see ``chunk_render.py`` for
the shared rationale on why sibling-method calls go through
``processor.<method>`` rather than a direct module-to-module call).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import TYPE_CHECKING

import numpy as np

from core.chunk_content_profile import store_content_profile
from core.encoding import WAVEncoderError, read_chunk_wav

from .chunk_render_miss import render_chunk
from .chunk_single_flight import chunk_flights
from .chunk_stream_state import (
    ChunkCancelledError,
    _invalidate_after_post_dsp_failure,
    _raise_if_cancelled,
    _raise_if_dsp_fallback,
)

if TYPE_CHECKING:
    from core.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger("core.chunked_processor")


def _serve_cached(
    processor: "ChunkedAudioProcessor", chunk_index: int
) -> tuple[str, np.ndarray] | None:
    """The chunk from the in-memory tier, then the on-disk WAV (#4792), or None on a miss.

    The cache holds the raw emitted segment, same shape as a fresh render (native
    channels, always 2-D; not load_audio's whole-file downmix contract, #5947).
    Smoothing it is this stream's step, exactly as for a miss: smooth_transition
    compares it to the chunk this processor served before it, in stream order (#5948).
    """
    cached_path = processor._lookup_cached_chunk(chunk_index)
    if cached_path is None:
        return None
    assert processor.total_chunks is not None
    logger.info(f"Serving cached chunk {chunk_index}/{processor.total_chunks}")
    try:
        audio = read_chunk_wav(cached_path)
    except (OSError, RuntimeError) as exc:  # RuntimeError: libsndfile
        # The file went away (or was cut) between lookup and read, e.g. to the
        # disk reaper: fall through to a re-render (#5967).
        logger.warning(f"Cached chunk {chunk_index} unreadable ({exc}); re-rendering")
        return None
    return (str(cached_path), processor._smooth_level_transition(audio, chunk_index))


def process_chunk(
    processor: "ChunkedAudioProcessor",
    chunk_index: int,
    locked: bool = False,
) -> tuple[str, np.ndarray]:
    """
    Process a single chunk with Auralis HybridProcessor and save to WAV.

    Returns both the path (for caching) and the numpy array (for streaming).
    This avoids the disk round-trip of saving then immediately reading back.

    Args:
        locked: If True, hold _processor_lock (threading.Lock) for the whole
            chunk so concurrent calls serialise. Used by process_chunk_safe,
            which runs this in a thread pool (#2388). Default False keeps the
            direct sync call lock-free; that is for tests (#4245), not for a
            caller sharing the processor with a stream (#6086).

    Returns:
        Tuple of (path_to_chunk_file, processed_audio_array)
    """
    if locked:
        with processor._processor_lock:
            return processor.process_chunk(chunk_index, locked=False)

    # Keep the range check below every public processing entry point. This
    # must happen before cache lookup so a stale out-of-range cache file can
    # never bypass the authoritative processor bound (#4733).
    processor._validate_chunk_index(chunk_index)

    cached = _serve_cached(processor, chunk_index)
    if cached is not None:
        return cached

    # One render per cache key across every processor (#5258): a follower waits for
    # the leader, then serves the WAV it wrote; if the leader was cancelled or failed
    # there is no file, and the follower claims the key itself.
    while True:
        flight = chunk_flights.claim(processor._path_cache.cache_key(chunk_index))
        if flight.leader:
            break
        flight.wait_for_leader(lambda: _raise_if_cancelled(processor, chunk_index))
        cached = _serve_cached(processor, chunk_index)
        if cached is not None:
            return cached
    try:
        return render_chunk(processor, chunk_index)
    finally:
        chunk_flights.release(flight)


async def process_chunk_safe(
    processor: "ChunkedAudioProcessor", chunk_index: int
) -> tuple[str, np.ndarray]:
    """
    Process a single chunk with thread-safe locking (async version).

    Offloads the CPU-intensive DSP work (HPSS, EQ, loudness normalization) to a
    thread-pool worker via asyncio.to_thread(), keeping the event loop free to handle
    WebSocket heartbeats, pause/seek commands, and other coroutines during the
    5-30 second processing window (issue #2388).

    Serialisation is provided by _processor_lock (threading.Lock): concurrent
    calls block in the thread pool rather than on the event loop.

    Returns:
        Tuple of (path_to_chunk_file, processed_audio_array)
        - path: for caching/durability
        - audio: numpy array for immediate streaming (avoids disk round-trip)
    """
    # Dedicated streaming pool, not the shared default executor (#5086):
    # this is the per-chunk hot path, and queueing behind an unrelated
    # repository call or the library scan makes CHUNK_PROCESS_TIMEOUT
    # (#3852) fire on queueing delay rather than a genuine DSP hang.
    from .executors import run_in_stream_executor

    return await run_in_stream_executor(processor.process_chunk, chunk_index, True)


def get_wav_chunk_path(processor: "ChunkedAudioProcessor", chunk_index: int) -> str:
    """
    Get WAV chunk for unified streaming architecture.

    This is the PRIMARY output method for the unified architecture.
    Process audio and encode directly to WAV in a single pass.
    WAV format is required for Web Audio API compatibility.

    Returns:
        Path to WAV chunk file
    """
    assert processor.sample_rate is not None and processor.total_chunks is not None and processor.total_duration is not None
    # Validate before cache/disk lookup. The shared validator is also used
    # by process_chunk and _process_chunk_core so worker-driven processing
    # cannot bypass the ceiling (#4342, #4733).
    processor._validate_chunk_index(chunk_index)
    # _sync_cache_lock serialises the full check→process→cache cycle so that
    # two concurrent thread-pool calls for the same chunk cannot both miss the
    # cache, both process the chunk, and produce conflicting results.
    with processor._sync_cache_lock:
        # Check cache — in-memory, then on-disk WAV (#4792: shared with process_chunk()
        # via _lookup_cached_chunk, as both write the exact same on-disk file).
        cached_path = processor._lookup_cached_chunk(chunk_index)
        if cached_path is not None:
            logger.info(f"Serving cached WAV chunk {chunk_index}")
            return str(cached_path)

        # Get WAV output path
        wav_chunk_path = processor._get_wav_chunk_path(chunk_index)

        # #5328 SIBLING: same cancel polling as process_chunk.
        _raise_if_cancelled(processor, chunk_index)

        logger.info(f"Processing chunk {chunk_index} directly to WAV")

        # LevelManager history and _dsp_state_advanced are only safe under
        # _processor_lock; this entry point used to mutate them without it, so a
        # caller mixing it with process_chunk could interleave rms/gain history
        # or clear the flag from the wrong call (#6086). Order: _sync_cache_lock
        # -> _processor_lock, as chunk_render already does.
        with processor._processor_lock:
            processor._dsp_state_advanced = False
            try:
                # Use shared core processing logic (eliminates duplicate code)
                # The raw emitted segment: the durable file is never level-smoothed (#5948).
                extracted_chunk = processor._process_chunk_core(chunk_index)

                # #5328: never persist a render its stream abandoned mid-DSP.
                _raise_if_cancelled(processor, chunk_index)
                _raise_if_dsp_fallback(processor, chunk_index)  # #6444: no durable file for a fallback

                try:
                    processor._wav_encoder.encode_and_save(
                        audio=extracted_chunk,
                        sample_rate=processor.sample_rate,
                        chunk_path=wav_chunk_path,
                        subtype='PCM_16',
                    )
                    logger.info(f"Chunk {chunk_index} encoded to WAV: {wav_chunk_path.name}")
                except WAVEncoderError as e:
                    logger.error(f"WAV encoding failed for chunk {chunk_index}: {e}")
                    raise RuntimeError(f"Failed to encode chunk to WAV: {e}")

                # Cache under the same collapsed key process_chunk() uses.
                processor._path_cache.store(chunk_index, wav_chunk_path)
            except ChunkCancelledError:
                processor._dsp_state_advanced = False  # see process_chunk
                raise
            except Exception:
                _invalidate_after_post_dsp_failure(processor, chunk_index)
                raise
            processor._dsp_state_advanced = False

    # Store last_content_profile globally for visualizer API access
    # This allows the /api/processing/parameters endpoint to show real processing data.
    # Runs across concurrent asyncio.to_thread workers (#4341) — guarded by
    # chunk_content_profile's dedicated lock so a write here can't interleave
    # with a read in get_last_content_profile() from the event-loop thread.
    if processor.processor is not None:
        processor_profile = getattr(processor.processor, 'last_content_profile', None)
        if processor_profile and processor.preset is not None:
            store_content_profile(processor.preset, processor_profile)
            logger.debug(f"📊 Stored processing profile for preset '{processor.preset}'")

    return str(wav_chunk_path)
