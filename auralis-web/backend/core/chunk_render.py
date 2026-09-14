#!/usr/bin/env python3

"""
Chunk Rendering — Hybrid-Processor Invocation + Level Smoothing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The per-chunk DSP wiring extracted from ``ChunkedAudioProcessor`` (#4245):
loading a chunk with context, invoking ``AudioProcessingPipeline`` (the
HybridProcessor front door), trimming context back off, and smoothing level
transitions across chunk boundaries.

Each function takes the owning ``ChunkedAudioProcessor`` as its first
argument and reads/updates its state directly — the same pattern already
used by ``chunk_mastering.compute_mastering_recommendation`` and
``chunk_crossfade.apply_crossfade_between_chunks``. Calls that recurse back
into another extracted concern go through ``processor.<method>`` (the
instance's own — possibly test-patched — attribute), never straight to a
sibling module function, so per-instance mocking (``patch.object(processor,
...)``) keeps working exactly as it did when the code lived on the class.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import TYPE_CHECKING, cast

import numpy as np

from core.audio_processing_pipeline import AudioProcessingPipeline
from core.chunk_boundaries import CHUNK_DURATION, CHUNK_INTERVAL, OVERLAP_DURATION
from core.chunk_operations import ChunkOperations

if TYPE_CHECKING:
    from core.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger("core.chunked_processor")


# ---------------------------------------------------------------------------
# Cache-hit level registry (#4669)
# ---------------------------------------------------------------------------
#
# A chunk served straight from the path cache (the in-memory dict tier or the
# on-disk WAV tier) never goes through process_chunk_core, so the LevelManager
# would never see it — see note_cached_chunk_level below for why that breaks
# the next cache-MISS chunk. Recording it needs two numbers the cached bytes
# alone don't carry cheaply:
#
#   * the RMS of the emitted segment (a decode away, which the path-only
#     caller get_wav_chunk_path must not pay on a per-chunk path), and
#   * the trailing gain smooth_transition baked into those samples — #4367
#     established that recording 0.0 when the real gain is known desyncs the
#     following chunk's ramp.
#
# Both are known at the instant the WAV is written, so chunk_streaming records
# them here keyed by the collapsed chunk cache key (#4792), which already
# encodes track / file signature / preset / intensity / targets hash / chunk
# index — i.e. exactly the identity of the bytes on disk.
#
# Process-wide rather than per-processor on purpose: the numbers describe the
# FILE, while every stream of a track builds its own ChunkedAudioProcessor with
# its own LevelManager. A per-instance map would miss precisely the
# cross-stream hits (back-seeks, a second play of the same track) that #4669 is
# about. Entries are small (two floats) and LRU-bounded.
#
# A hit with no remembered entry — the WAV survives on disk from an earlier run
# of the process — degrades to "unity trailing gain", the same default
# note_cached_chunk_level has always carried, never to "skip the recording".
_MAX_REMEMBERED_LEVELS = 4096
_chunk_levels: "OrderedDict[str, tuple[float, float]]" = OrderedDict()
_chunk_levels_lock = threading.Lock()


def remember_chunk_level(cache_key: str, rms_db: float, gain_db: float) -> None:
    """Record the level a just-written chunk WAV was encoded at (#4669)."""
    with _chunk_levels_lock:
        _chunk_levels[cache_key] = (rms_db, gain_db)
        _chunk_levels.move_to_end(cache_key)
        while len(_chunk_levels) > _MAX_REMEMBERED_LEVELS:
            _chunk_levels.popitem(last=False)


def recall_chunk_level(cache_key: str) -> tuple[float, float] | None:
    """``(rms_db, gain_db)`` for a cached chunk, or None if this process never
    wrote it (#4669)."""
    with _chunk_levels_lock:
        entry = _chunk_levels.get(cache_key)
        if entry is not None:
            _chunk_levels.move_to_end(cache_key)
        return entry


def reset_chunk_levels() -> None:
    """Forget every remembered chunk level. Test hook — the registry is
    process-wide, so a test that asserts on a cache-hit recording must start
    from a known state."""
    with _chunk_levels_lock:
        _chunk_levels.clear()


def load_chunk(
    processor: "ChunkedAudioProcessor", chunk_index: int, with_context: bool = True
) -> tuple[np.ndarray, float, float]:
    """
    Load a single chunk from audio file with optional context.

    DELEGATES TO: ChunkOperations.load_chunk_from_file() (Phase 3 refactoring)

    Returns:
        Tuple of (audio_chunk, chunk_start_time, chunk_end_time)
    """
    assert processor.sample_rate is not None

    # Resolve to a libsndfile-seekable path ONCE per track. For .m4a/.aac/
    # .wma libsndfile cannot open the source at all, so without this every
    # chunk fell through load_chunk_from_file's except branch into a
    # whole-file FFmpeg decode — ~60 full decodes for a 10-minute track
    # (#4737). Native formats (mp3/ogg/flac/wav) resolve to the original
    # path and pay only a header open, so nothing regresses for them.
    seekable_path = processor._source.resolve()

    return ChunkOperations.load_chunk_from_file(
        filepath=seekable_path,
        chunk_index=chunk_index,
        sample_rate=processor.sample_rate,
        chunk_duration=CHUNK_DURATION,
        chunk_interval=CHUNK_INTERVAL,
        overlap_duration=OVERLAP_DURATION,
        with_context=with_context,
        total_duration=processor.total_duration,
    )


def calculate_rms(processor: "ChunkedAudioProcessor", audio: np.ndarray) -> float:
    """Calculate RMS level of audio in dB. Delegates to LevelManager."""
    return float(processor._level_manager.calculate_rms(audio))


def smooth_level_transition(
    processor: "ChunkedAudioProcessor", chunk: np.ndarray, chunk_index: int
) -> np.ndarray:
    """
    Smooth level transitions between chunks by limiting maximum level changes.

    Delegates to LevelManager. This prevents volume jumps by ensuring the
    current chunk's RMS doesn't differ too much from the previous chunk's RMS.

    Returns:
        Level-smoothed chunk
    """
    # Use LevelManager to smooth transitions. Pass the sample rate so the
    # gain-ramp window is sized correctly (#3831).
    chunk_adjusted, gain_db, was_adjusted = processor._level_manager.smooth_transition(
        chunk=chunk,
        chunk_index=chunk_index,
        apply_adjustment=True,
        sample_rate=processor.sample_rate or 44100,
    )

    if was_adjusted:
        current_rms = processor._level_manager.current_rms
        adjusted_rms = calculate_rms(processor, chunk_adjusted)
        logger.info(
            f"Chunk {chunk_index}: Smoothed level transition "
            f"(original RMS: {current_rms:.1f} dB, "
            f"adjusted RMS: {adjusted_rms:.1f} dB, "
            f"gain adjustment: {gain_db:.2f} dB)"
        )
    else:
        current_rms = processor._level_manager.current_rms
        logger.info(
            f"Chunk {chunk_index}: Level transition OK "
            f"(RMS: {current_rms:.1f} dB)"
        )

    # Update legacy history tracking for backward compatibility
    history = processor._level_manager.history
    gain_adjustments = processor._level_manager.gain_adjustments
    processor.chunk_rms_history = list(history) if hasattr(history, '__iter__') else []
    processor.chunk_gain_history = list(gain_adjustments) if hasattr(gain_adjustments, '__iter__') else []

    return cast(np.ndarray, chunk_adjusted)


def note_cached_chunk_level(
    processor: "ChunkedAudioProcessor",
    chunk: np.ndarray | None,
    chunk_index: int,
    gain_db: float = 0.0,
    rms_db: float | None = None,
) -> None:
    """Record a cache-hit chunk's level into the LevelManager (#3832).

    A cached chunk is returned without going through process_chunk_core, so
    the LevelManager would otherwise never see it — leaving rms_history out
    of chronological sync, so a later cache-MISS chunk smooths against the
    wrong previous RMS. We RECORD the cached chunk's RMS and its true
    trailing gain (`gain_db`, captured when the chunk was originally cached)
    without re-adjusting the already-smoothed audio, under the same
    _processor_lock the processing path uses so the history deque is never
    touched concurrently. Using the true gain instead of unconditionally
    recording 0.0 keeps a subsequent cache-MISS chunk's ramp baseline
    correct (#4367).

    ``rms_db`` (#4669) lets a caller that already knows the cached chunk's
    level — from the registry above — record it without decoding the WAV, for
    the path-only cache-hit branch in get_wav_chunk_path. When it is None the
    RMS is computed from ``chunk``, which must then be present.
    """
    with processor._processor_lock:
        processor._level_manager.record_cached_level(
            chunk=chunk,
            chunk_index=chunk_index,
            gain_db=gain_db,
            rms_db=rms_db,
        )
        # Keep the legacy history mirrors in sync (matches smooth_level_transition).
        history = processor._level_manager.history
        gain_adjustments = processor._level_manager.gain_adjustments
        processor.chunk_rms_history = list(history) if hasattr(history, '__iter__') else []
        processor.chunk_gain_history = list(gain_adjustments) if hasattr(gain_adjustments, '__iter__') else []


def process_chunk_core(
    processor: "ChunkedAudioProcessor", chunk_index: int, fast_start: bool = False
) -> np.ndarray:
    """
    Core chunk processing logic (shared by process_chunk and get_wav_chunk_path).

    DELEGATES TO: AudioProcessingPipeline.process_audio() (Phase 1 refactoring).
    This is a thin wrapper that:
    1. Loads chunk with context
    2. Delegates to unified pipeline for processing
    3. Trims context and smooths levels

    Returns:
        Processed audio chunk (context trimmed, intensity blended, levels smoothed)
    """
    processor._validate_chunk_index(chunk_index)
    assert processor.sample_rate is not None
    # Load chunk with context
    audio_chunk, chunk_start, chunk_end = processor.load_chunk(chunk_index, with_context=True)

    # DELEGATE TO UNIFIED PIPELINE (Phase 1 refactoring, updated Phase 2)
    # This replaces ~80 lines of duplicate processing logic with single call
    processed_chunk = AudioProcessingPipeline.process_audio(
        audio=audio_chunk,
        preset=processor.preset,
        intensity=processor.intensity,
        processor_factory=processor._processor_factory,  # Phase 2: Use ProcessorFactory
        track_id=processor.track_id,
        # #5306: this is the call that actually resolves the processor doing the
        # DSP — the factory is re-queried per chunk, so passing the rate-aware
        # config ONLY at init time (chunk_processor_init) would have left every
        # chunk rendered by a separate, 44.1 kHz-assuming cache entry.
        config=processor.processor_config,
        targets=processor.mastering_targets,
        fast_start=fast_start,
        chunk_index=chunk_index,
        allow_empty=False  # Don't allow empty chunks
    )
    # The shared HybridProcessor has now advanced. If any validation or write
    # below this point fails, chunk_streaming must invalidate that cached
    # processor before a retry of this chunk (#5274).
    processor._dsp_state_advanced = processor.preset is not None

    # Trim context (keep only the actual chunk) (Phase 5.1: Using ChunkBoundaryManager)
    processed_chunk = processor._boundary_manager.trim_context(processed_chunk, chunk_index)

    # Validate chunk is not empty before smooth transitions
    if len(processed_chunk) == 0:
        logger.error(f"Chunk {chunk_index} is empty after context trimming. Returning silence.")
        num_channels = audio_chunk.shape[1] if audio_chunk.ndim > 1 else 2
        assert processor.sample_rate is not None
        # Preserve the input dtype rather than hardcoding float32 (#3831
        # sibling) so the fallback matches a float64 pipeline if present.
        processed_chunk = np.zeros((processor.sample_rate // 10, num_channels), dtype=audio_chunk.dtype)  # 100ms silence

    # CRITICAL FIX: Smooth level transitions between chunks
    # This prevents volume jumps by limiting maximum RMS changes
    processed_chunk = processor._smooth_level_transition(processed_chunk, chunk_index)

    return processed_chunk
