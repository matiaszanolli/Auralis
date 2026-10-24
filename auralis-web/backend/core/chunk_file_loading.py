#!/usr/bin/env python3

"""
Chunk File Loading
~~~~~~~~~~~~~~~~~~

``load_chunk_from_file`` split out of ``ChunkOperations`` (#6270): the
on-disk chunk reader (with the #4737 seekable-source path) is independent of
segment extraction. See ``seekable_source.py`` for why this no longer opens
the raw track path.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""



import logging

import numpy as np

from core.chunk_boundary_manager import ChunkBoundaryManager
from core.chunk_boundaries import (
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    CONTEXT_DURATION,
    OVERLAP_DURATION,
)

logger = logging.getLogger(__name__)


def load_chunk_from_file(
    filepath: str,
    chunk_index: int,
    sample_rate: int,
    chunk_duration: float = CHUNK_DURATION,
    chunk_interval: float = CHUNK_INTERVAL,
    with_context: bool = True,
    total_duration: float | None = None
) -> tuple[np.ndarray, float, float]:
    """
    Load a single chunk from audio file with optional context.

    Consolidates logic from:
    - chunked_processor.load_chunk()

    Chunks after the first include OVERLAP_DURATION at the start for crossfading.
    This ensures no audio is lost during crossfade concatenation.

    Args:
        filepath: Path to audio file
        chunk_index: Index of chunk to load (0-based)
        sample_rate: Sample rate of audio
        chunk_duration: Duration of each chunk in seconds (actual chunk length).
            Only used when total_duration is None — see below.
        chunk_interval: Interval between chunk starts (for overlap model).
            Only used when total_duration is None — see below.
        with_context: Include context before/after for better processing
        total_duration: Total duration of audio, if known. When provided,
            boundaries are derived from ChunkBoundaryManager — the same
            authority trim_context() uses — instead of being re-derived
            here, so the load and trim halves of the pipeline cannot
            structurally desync (the #3807 failure mode; fixes #5055).
            ChunkBoundaryManager always uses chunk_boundaries.py's
            module-level CHUNK_DURATION/CHUNK_INTERVAL/CONTEXT_DURATION,
            so chunk_duration/chunk_interval above are ignored in this
            case — true of every current caller, which already pass
            those same constants through. When None (duration not yet
            known), falls back to the original unbounded derivation
            using chunk_duration/chunk_interval directly.

    Returns:
        Tuple of (audio_chunk, chunk_start_time, chunk_end_time)
    """
    if total_duration is not None:
        boundary_manager = ChunkBoundaryManager(
            total_duration=total_duration, sample_rate=sample_rate
        )
        load_start, load_end, chunk_start, chunk_end = boundary_manager.get_chunk_boundaries(
            chunk_index, with_context=with_context
        )
    else:
        # No known total_duration (e.g. probing before metadata is
        # loaded) — ChunkBoundaryManager requires one, so fall back to
        # the original, unbounded derivation. chunk_end/load_end are NOT
        # capped here; test_fallback_start_beyond_eof_returns_float32
        # deliberately exercises this uncapped path.
        if chunk_index == 0:
            chunk_start = 0.0
            chunk_end = chunk_start + chunk_duration
        else:
            chunk_start = chunk_index * chunk_interval
            chunk_end = chunk_start + chunk_duration
        context_duration = CONTEXT_DURATION if with_context else 0.0
        load_start = max(0.0, chunk_start - context_duration)
        load_end = chunk_end + context_duration

    # An out-of-range chunk_index (beyond total_duration) collapses this
    # window to empty or inverted once chunk_end is capped above. Bail out
    # here instead of letting the soundfile read fail and fall through to
    # the full-file-decode fallback below — that fallback is a small-
    # request -> large-work amplifier for an out-of-bounds index (#4342).
    if load_start >= load_end:
        logger.warning(
            f"Chunk {chunk_index} window is empty/inverted "
            f"(start={load_start:.1f}s, end={load_end:.1f}s) — out of range, returning silence"
        )
        silence = np.zeros((int(0.1 * sample_rate), 2), dtype=np.float32)
        return silence, chunk_start, chunk_end

    # Load audio segment
    try:
        import soundfile as sf

        start_frame = int(round(load_start * sample_rate))
        frames_to_read = int(round((load_end - load_start) * sample_rate))

        with sf.SoundFile(filepath) as f:
            f.seek(start_frame)
            # dtype defaults to float64 with no dtype= arg (#4794) — every
            # other read/fallback in this pipeline (load_audio below,
            # stream_normal.py, the silence fallbacks) is float32, so an
            # unspecified dtype here silently double-precisions the DSP
            # working set on the primary (non-fallback) load path.
            # always_2d=True replaces the manual ndim fix-up below.
            audio = f.read(frames_to_read, dtype='float32', always_2d=True)

    except Exception as e:
        logger.warning(f"Soundfile loading failed, using fallback: {e}")
        # Fallback: load entire audio and slice
        from auralis.io.unified_loader import load_audio

        full_audio, _ = load_audio(filepath, target_sample_rate=sample_rate)

        start_sample = int(round(load_start * sample_rate))
        end_sample = int(round(load_end * sample_rate))

        # Ensure we don't try to read beyond the file
        end_sample = min(end_sample, len(full_audio))

        if start_sample >= len(full_audio):
            logger.error(
                f"Chunk {chunk_index} start ({start_sample}) beyond file length ({len(full_audio)})"
            )
            num_ch = full_audio.shape[1] if full_audio.ndim > 1 else 1
            audio = np.zeros((1, num_ch), dtype=np.float32)
        else:
            audio = full_audio[start_sample:end_sample]

    # Validate that we loaded something
    if len(audio) == 0:
        logger.error(
            f"Chunk {chunk_index} resulted in empty audio "
            f"(start={load_start:.1f}s, end={load_end:.1f}s)"
        )
        # Return minimal silence instead of empty array
        num_channels = audio.shape[1] if audio.ndim > 1 else 1
        audio = np.zeros((int(0.1 * sample_rate), num_channels), dtype=np.float32)
        logger.warning(f"Returning 100ms of silence for chunk {chunk_index}")

    return audio, chunk_start, chunk_end
