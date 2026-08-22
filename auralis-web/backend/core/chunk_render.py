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
:license: GPLv3
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import numpy as np

from core.audio_processing_pipeline import AudioProcessingPipeline
from core.chunk_boundaries import CHUNK_DURATION, CHUNK_INTERVAL, OVERLAP_DURATION
from core.chunk_operations import ChunkOperations

if TYPE_CHECKING:
    from core.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger("core.chunked_processor")


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
    processor: "ChunkedAudioProcessor", chunk: np.ndarray, chunk_index: int, gain_db: float = 0.0
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
    """
    with processor._processor_lock:
        processor._level_manager.record_cached_level(
            chunk=chunk,
            chunk_index=chunk_index,
            gain_db=gain_db,
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
        targets=processor.mastering_targets,
        fast_start=fast_start,
        chunk_index=chunk_index,
        allow_empty=False  # Don't allow empty chunks
    )

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
