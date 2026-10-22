"""
Per-chunk cancellation, invalidation and level-recording helpers (split from
chunk_streaming.py, #5833). Each takes the owning ``ChunkedAudioProcessor``
as its first argument, like the entry points that call them.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import TYPE_CHECKING

import numpy as np

from core import chunk_render

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
    EXTRACTED segment (the bytes actually written). chunk_rms_history[-1]
    describes that same window since #5051, but measuring the bytes
    themselves is what makes the registry value and a decode interchangeable. The gain is the trailing value smooth_transition left in
    chunk_gain_history, exactly as stream_chunk_ops captures it for the
    in-memory tier (#4367).

    Best-effort: bookkeeping for a chunk that has already been written
    durably, so it must never turn a successful render into a failure.
    """
    try:
        gain_history = processor._level_manager.gain_history
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
