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
:license: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from core import chunk_render
from core.chunk_boundaries import CHUNK_DURATION, CHUNK_INTERVAL, OVERLAP_DURATION
from core.chunk_content_profile import store_content_profile
from core.chunk_operations import ChunkOperations
from core.encoding import WAVEncoderError

if TYPE_CHECKING:
    from core.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger("core.chunked_processor")


class ChunkCancelledError(Exception):
    """Raised when a chunk's owning stream was cancelled before/during DSP
    (#4815). Distinguishes a deliberately-abandoned chunk from a genuine
    processing failure — callers must not log/retry it as one. In practice
    the coroutine that would have awaited this chunk has almost always
    already unwound via CancelledError by the time this is raised (asyncio
    cancellation doesn't wait for the underlying executor thread), so this
    exists mainly to cut the wasted DSP work short rather than to be
    observed by a live caller."""


def _raise_if_cancelled(processor: "ChunkedAudioProcessor", chunk_index: int) -> None:
    """Abandon a chunk whose owning stream was cancelled (#4815, #5328).

    ``task.cancel()`` on the streaming coroutine cannot stop DSP already
    running in an executor thread, so the chunk-rendering functions poll the
    per-stream cancel event themselves: once before DSP, to skip the work, and
    again right before the durable write, so a render the stream abandoned
    mid-DSP is never persisted.
    """
    cancel_event = getattr(processor, "_cancel_event", None)
    if cancel_event is not None and cancel_event.is_set():
        raise ChunkCancelledError(
            f"Chunk {chunk_index} abandoned: owning stream was cancelled"
        )


def _invalidate_after_post_dsp_failure(
    processor: "ChunkedAudioProcessor", chunk_index: int
) -> None:
    """Ensure a retry cannot reuse a stateful processor advanced by this chunk."""
    if not getattr(processor, "_dsp_state_advanced", False):
        return
    processor._dsp_state_advanced = False
    invalidate_pooled_processor(processor, chunk_index, "failed after DSP state advanced")


def invalidate_pooled_processor(
    processor: "ChunkedAudioProcessor", chunk_index: int, reason: str
) -> None:
    """Discard the pooled HybridProcessor this chunk rendered on.

    ProcessorFactory hands one cached instance to every stream of a track, so
    an instance left in an unknown state must be dropped for the next stream
    to build a fresh one. Used after a post-DSP failure (#5274) and after a
    chunk DSP timeout (#5335), where the abandoned executor thread may still
    be advancing the instance.
    """
    if processor.preset is None:
        return
    processor._processor_factory.invalidate(
        track_id=processor.track_id,
        preset=processor.preset,
        mastering_targets=processor.mastering_targets,
        # #5306: `invalidate` rebuilds the cache key, and `_get_config_hash`
        # maps None to "default". Once this track's processor is keyed on a
        # rate-aware config, omitting it here pops nothing and leaves the
        # DSP-advanced instance cached for the retry — exactly the #5274
        # failure this function exists to prevent.
        config=processor.processor_config,
    )
    # Processing selects from the factory on every call; this is only an
    # observational handle to the instance created during initialization.
    processor.processor = None
    logger.error(
        "Chunk %s %s; invalidated the cached processor so a retry starts fresh",
        chunk_index,
        reason,
    )


def _remember_written_chunk_level(
    processor: "ChunkedAudioProcessor", chunk_index: int, extracted_chunk: np.ndarray
) -> None:
    """Record what level this chunk's WAV was just encoded at (#4669).

    Stored against the collapsed chunk cache key so a later cache HIT — in
    this stream or any other stream of the same track — can feed the
    LevelManager without decoding the file. The RMS is taken from the
    EXTRACTED segment (the bytes actually written), not from
    chunk_rms_history[-1], which describes the wider pre-extraction render
    window; matching the file is what makes the registry value and a decode
    interchangeable. The gain is the trailing value smooth_transition left in
    chunk_gain_history, exactly as stream_chunk_ops captures it for the
    in-memory tier (#4367).

    Best-effort: bookkeeping for a chunk that has already been written
    durably, so it must never turn a successful render into a failure.
    """
    try:
        gain_history = getattr(processor, "chunk_gain_history", None)
        gain_db = float(gain_history[-1]) if gain_history else 0.0
        chunk_render.remember_chunk_level(
            processor._path_cache.cache_key(chunk_index),
            rms_db=float(processor._calculate_rms(extracted_chunk)),
            gain_db=gain_db,
        )
    except Exception as e:  # pragma: no cover - defensive
        logger.debug(f"Could not remember chunk {chunk_index} level (not critical): {e}")


def _record_cache_hit_level(
    processor: "ChunkedAudioProcessor",
    chunk_index: int,
    audio: np.ndarray | None = None,
) -> None:
    """Feed a cache-HIT chunk into the LevelManager (#4669).

    #3832 established that a hit must still be recorded, or rms_history holds
    a stale, non-adjacent chunk when the next cache-MISS chunk is smoothed and
    smooth_transition steps the boundary. That recording was wired only into
    the in-memory tier in stream_chunk_ops.process_chunk_only; the two
    path-cache hit branches in this module returned early without it. This is
    the same call, for the dict/on-disk tier (both of which
    _lookup_cached_chunk collapses into one branch since #4792).

    `audio` is passed when the caller already decoded the chunk (process_chunk
    must return the samples anyway, so its RMS is free and authoritative for
    the bytes on disk). get_wav_chunk_path returns only a path and passes
    None: its RMS comes from the registry, so this stays decode-free.

    Executor placement (#5327 convention): both callers are synchronous and
    already run ON the streaming pool — get_wav_chunk_path is submitted to it
    by routers/enhancement, process_chunk by process_chunk_safe — so this runs
    inline. Re-submitting to run_in_stream_executor from inside a pool thread
    would be a blocking self-dispatch, not the fix #5327 made at its async
    call site. `_processor_lock` is an RLock, so the inline acquisition below
    re-enters cleanly under process_chunk(locked=True).

    Best-effort: state-sync only, never fails a chunk fetch.
    """
    try:
        remembered = chunk_render.recall_chunk_level(
            processor._path_cache.cache_key(chunk_index)
        )
        if remembered is None:
            # WAV written by an earlier run of this process: the trailing gain
            # is unrecoverable, so fall back to unity — note_cached_chunk_level's
            # long-standing default.
            rms_db, gain_db = None, 0.0
        else:
            rms_db, gain_db = remembered
        if audio is None and rms_db is None:
            # Path-only caller with nothing remembered. Decoding purely to
            # record a level is the cost this registry exists to avoid, and
            # get_wav_chunk_path's only production caller is the background
            # pre-warm (routers/enhancement), whose throwaway processor's
            # LevelManager is discarded — so skip rather than decode.
            logger.debug(
                f"No remembered level for cached chunk {chunk_index}; "
                f"skipping the cache-hit recording rather than decoding"
            )
            return
        processor.note_cached_chunk_level(
            audio,
            chunk_index,
            gain_db,
            # Prefer the decoded samples when we have them: they ARE the
            # cached bytes, so their RMS cannot disagree with the file.
            None if audio is not None else rms_db,
        )
    except Exception as e:
        logger.debug(f"Cache-hit level recording skipped (not critical): {e}")


def process_chunk(
    processor: "ChunkedAudioProcessor",
    chunk_index: int,
    fast_start: bool = False,
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
            direct sync call (and tests) lock-free (#4245: collapses the old
            process_chunk / _process_chunk_locked pair).

    Returns:
        Tuple of (path_to_chunk_file, processed_audio_array)
    """
    if locked:
        with processor._processor_lock:
            return processor.process_chunk(chunk_index, fast_start, locked=False)

    # Keep the range check below every public processing entry point. This
    # must happen before cache lookup so a stale out-of-range cache file can
    # never bypass the authoritative processor bound (#4733).
    processor._validate_chunk_index(chunk_index)

    # Check cache first — in-memory, then on-disk WAV (#4792: this used to
    # check only the in-memory dict, so a fresh in-memory cache (every new
    # stream) always re-ran the full DSP pipeline even when a byte-identical
    # WAV from a previous stream of this track/preset/intensity was already
    # on disk).
    cached_path = processor._lookup_cached_chunk(chunk_index)

    if cached_path is not None:
        assert processor.total_chunks is not None
        logger.info(f"Serving cached chunk {chunk_index}/{processor.total_chunks}")
        # Load from disk only if cached (for subsequent requests)
        # For initial streaming, audio array is already in memory cache
        from auralis.io.unified_loader import load_audio
        audio, _ = load_audio(str(cached_path))
        # #4669: this hit bypasses _process_chunk_core, so without the line
        # below the LevelManager never sees this chunk and the NEXT cache-MISS
        # chunk smooths against a stale, non-adjacent RMS.
        _record_cache_hit_level(processor, chunk_index, audio=audio)
        return (str(cached_path), audio)

    # #4815: bail out before the expensive DSP call if the owning stream was
    # already cancelled (seek/track-change/disconnect) — cheap to check, and
    # avoids running 200ms-2s of DSP work (and holding the shared
    # HybridProcessor's _process_lock, blocking any NEW stream reusing the
    # same pooled processor) for a chunk nothing will ever consume.
    _raise_if_cancelled(processor, chunk_index)

    logger.info(f"Processing chunk {chunk_index}/{processor.total_chunks} (preset: {processor.preset}, fast_start: {fast_start})")

    # Skip synchronous fingerprint extraction during chunk processing.
    # Loading the full audio file to compute a fingerprint blocks the first
    # chunk for 5-30s (depending on file size/format), causing the frontend
    # to time out and re-send play requests.  The background fingerprint
    # queue handles extraction asynchronously; subsequent plays will use
    # the cached result.  HybridProcessor analyzes per-chunk as fallback.
    if processor.fingerprint is None and chunk_index == 0:
        logger.info(f"ℹ️  No cached fingerprint for track {processor.track_id} — using per-chunk adaptive processing")

    processor._dsp_state_advanced = False
    try:
        # Process chunk using shared core logic
        processed_chunk = processor._process_chunk_core(chunk_index, fast_start)

        # Extract the emitted, non-overlapping segment before durable encoding.
        assert (
            processor.sample_rate is not None
            and processor.total_chunks is not None
            and processor.total_duration is not None
        )
        extracted_chunk = ChunkOperations.extract_chunk_segment(
            processed_chunk=processed_chunk,
            chunk_index=chunk_index,
            sample_rate=processor.sample_rate,
            chunk_duration=CHUNK_DURATION,
            chunk_interval=CHUNK_INTERVAL,
            overlap_duration=OVERLAP_DURATION,
            total_chunks=processor.total_chunks,
            total_duration=processor.total_duration,
        )

        # #5328: a seek can land while this DSP is in flight — look-ahead
        # renders are mid-DSP for most of the pump loop — and the check above
        # has long passed. The durable cache key carries no stream identity
        # and a later disk hit is never re-smoothed (#4669), so an abandoned
        # render written here would bake in gain smoothed against a stream
        # nobody hears.
        _raise_if_cancelled(processor, chunk_index)

        # Saved for durability/caching; the array avoids an immediate readback.
        # #4666: targets_hash completes the on-disk identity — the write must
        # land at exactly the path ChunkPathCache.lookup_cached() will check.
        chunk_path = processor._wav_encoder.encode_and_save_from_path(
            audio=extracted_chunk,
            sample_rate=processor.sample_rate,
            track_id=processor.track_id,
            file_signature=processor.file_signature,
            preset=processor.preset,
            intensity=processor.intensity,
            chunk_index=chunk_index,
            subtype='PCM_16',
            targets_hash=processor.targets_hash,
        )
        processor._path_cache.store(chunk_index, chunk_path)
        # #4669: remember the level these bytes carry so a later hit on them
        # can be recorded without a decode.
        _remember_written_chunk_level(processor, chunk_index, extracted_chunk)
    except ChunkCancelledError:
        # Not a failed retry (#5274): nothing re-requests this chunk from the
        # cancelled stream, and the seek that cancelled it already breaks
        # processor continuity, exactly as when the look-ahead finished first.
        processor._dsp_state_advanced = False
        raise
    except Exception:
        _invalidate_after_post_dsp_failure(processor, chunk_index)
        raise
    processor._dsp_state_advanced = False

    logger.info(f"Chunk {chunk_index} processed and saved to {Path(chunk_path).name}")
    # Return both path (for caching) and audio array (for immediate streaming)
    return (str(chunk_path), extracted_chunk)


async def process_chunk_safe(
    processor: "ChunkedAudioProcessor", chunk_index: int, fast_start: bool = False
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

    return await run_in_stream_executor(processor.process_chunk, chunk_index, fast_start, True)


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
        # Check cache — in-memory, then on-disk WAV (#4792: shared with
        # process_chunk() via _lookup_cached_chunk, since both write the
        # exact same on-disk file under what used to be two different
        # cache keys — a hit recorded by one was invisible to the other).
        cached_path = processor._lookup_cached_chunk(chunk_index)
        if cached_path is not None:
            logger.info(f"Serving cached WAV chunk {chunk_index}")
            # #4669 SIBLING of the process_chunk branch above. Decode-free:
            # this path never loads the samples, so the level comes from the
            # registry populated when the WAV was written.
            _record_cache_hit_level(processor, chunk_index)
            return str(cached_path)

        # Get WAV output path
        wav_chunk_path = processor._get_wav_chunk_path(chunk_index)

        # #5328 SIBLING: same cancel polling as process_chunk.
        _raise_if_cancelled(processor, chunk_index)

        logger.info(f"Processing chunk {chunk_index} directly to WAV")

        processor._dsp_state_advanced = False
        try:
            # Use shared core processing logic (eliminates duplicate code)
            processed_chunk = processor._process_chunk_core(chunk_index, fast_start=False)

            extracted_chunk = ChunkOperations.extract_chunk_segment(
                processed_chunk=processed_chunk,
                chunk_index=chunk_index,
                sample_rate=processor.sample_rate,
                chunk_duration=CHUNK_DURATION,
                chunk_interval=CHUNK_INTERVAL,
                overlap_duration=OVERLAP_DURATION,
                total_chunks=processor.total_chunks,
                total_duration=processor.total_duration,
            )

            # #5328: never persist a render its stream abandoned mid-DSP.
            _raise_if_cancelled(processor, chunk_index)

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
            # #4669: see process_chunk's matching call.
            _remember_written_chunk_level(processor, chunk_index, extracted_chunk)
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
