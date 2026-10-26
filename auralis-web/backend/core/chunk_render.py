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
used by ``chunk_mastering.compute_mastering_recommendation``. Calls that recurse back
into another extracted concern go through ``processor.<method>`` (the
instance's own — possibly test-patched — attribute), never straight to a
sibling module function, so per-instance mocking (``patch.object(processor,
...)``) keeps working exactly as it did when the code lived on the class.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import TYPE_CHECKING, cast

import numpy as np

from core.audio_processing_pipeline import AudioProcessingPipeline
from core.chunk_boundaries import CHUNK_DURATION, CHUNK_INTERVAL
from core.chunk_file_loading import load_chunk_from_file
from core.chunk_segment_extraction import extract_chunk_segment

if TYPE_CHECKING:
    from core.chunked_processor import ChunkedAudioProcessor

logger = logging.getLogger("core.chunked_processor")


def load_chunk(
    processor: "ChunkedAudioProcessor", chunk_index: int, with_context: bool = True
) -> tuple[np.ndarray, float, float]:
    """
    Load a single chunk from audio file with optional context.

    DELEGATES TO: load_chunk_from_file() in chunk_file_loading.py (#6270 split)

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

    return load_chunk_from_file(
        filepath=seekable_path,
        chunk_index=chunk_index,
        sample_rate=processor.sample_rate,
        chunk_duration=CHUNK_DURATION,
        chunk_interval=CHUNK_INTERVAL,
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

    return cast(np.ndarray, chunk_adjusted)


def process_chunk_core(
    processor: "ChunkedAudioProcessor", chunk_index: int, fast_start: bool = False
) -> np.ndarray:
    """
    Core chunk processing logic (shared by process_chunk and get_wav_chunk_path).

    DELEGATES TO: AudioProcessingPipeline.process_audio() (Phase 1 refactoring).
    This is a thin wrapper that:
    1. Loads chunk with context
    2. Delegates to unified pipeline for processing
    3. Trims context and extracts the emitted segment

    Returns:
        The emitted segment: context trimmed, overlap skipped. NOT level
        smoothed: this is what the durable chunk cache stores, and it must not
        depend on which chunk this processor happened to render before (#5948).
        Smoothing is a per-stream, serve-time step - see `smooth_level_transition`
        and `chunk_streaming.process_chunk`.
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
        # The stream's own leased HybridProcessor (#6091) -- not re-selected from
        # the shared factory per chunk, where two streams of one track would be
        # handed the same instance. Its lease was taken with the rate-aware
        # config (#5306), see ChunkedAudioProcessor.hybrid_processor().
        processor=processor.hybrid_processor(),
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
        # Preserve the input dtype rather than hardcoding float32 (#3831
        # sibling) so the fallback matches a float64 pipeline if present.
        processed_chunk = np.zeros((processor.sample_rate // 10, num_channels), dtype=audio_chunk.dtype)  # 100ms silence

    # Extract the emitted segment (#5051). Serve-time smoothing ramps from sample
    # 0 of exactly these bytes, so the heard boundary is the one that is measured.
    assert processor.total_chunks is not None and processor.total_duration is not None
    processed_chunk = extract_chunk_segment(
        processed_chunk=processed_chunk,
        chunk_index=chunk_index,
        sample_rate=processor.sample_rate,  # geometry: chunk_boundaries defaults
        total_chunks=processor.total_chunks,
        total_duration=processor.total_duration,
    )

    return processed_chunk
