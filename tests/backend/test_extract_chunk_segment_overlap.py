#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for ChunkOperations.extract_chunk_segment overlap handling.

CONTEXT (BE-CP-1 / #3803): For middle chunks, the context-trimmed buffer
represents source time ``[chunk_start, chunk_start + CHUNK_DURATION]`` (~15 s).
Chunk 0 emits the full first ``CHUNK_DURATION``, whose tail overlaps the first
``OVERLAP_DURATION`` seconds of every subsequent buffer. ``extract_chunk_segment``
must therefore SKIP that overlap on middle chunks and emit the next
``CHUNK_INTERVAL`` — otherwise the overlap is re-emitted, producing an audible
5-second backward jump at every chunk 0 -> 1 boundary.

These tests encode each sample's absolute *source* sample index as its value, so
a backward jump (re-emitted audio) is detectable as a non-monotonic value
sequence after concatenation.

:license: GPLv3
"""

import sys
from pathlib import Path

import numpy as np

backend_path = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(backend_path))

from core.chunk_operations import ChunkOperations
from core.chunked_processor import CHUNK_DURATION, CHUNK_INTERVAL, OVERLAP_DURATION

SR = 8000  # low rate keeps arrays small and source indices exactly float-representable


def _post_trim_buffer(chunk_index: int, channels: int = 2) -> np.ndarray:
    """Simulate the context-trimmed buffer handed to extract_chunk_segment.

    After ChunkBoundaryManager.trim_context(), a (non-capped) middle chunk's
    buffer spans source time [chunk_start, chunk_start + CHUNK_DURATION], and
    chunk 0's buffer spans [0, CHUNK_DURATION]. Each sample's value is its
    absolute source sample index, so reconstruction can be checked directly.
    """
    chunk_start_s = 0 if chunk_index == 0 else chunk_index * CHUNK_INTERVAL
    start_idx = int(round(chunk_start_s * SR))
    length = int(round(CHUNK_DURATION * SR))
    ramp = np.arange(start_idx, start_idx + length, dtype=np.float64)
    return np.column_stack([ramp] * channels)


def _extract(chunk_index: int, total_chunks: int, total_duration: float) -> np.ndarray:
    return ChunkOperations.extract_chunk_segment(
        processed_chunk=_post_trim_buffer(chunk_index),
        chunk_index=chunk_index,
        sample_rate=SR,
        chunk_duration=CHUNK_DURATION,
        chunk_interval=CHUNK_INTERVAL,
        overlap_duration=OVERLAP_DURATION,
        total_chunks=total_chunks,
        total_duration=total_duration,
    )


def test_chunk_zero_emits_full_chunk_duration():
    seg = _extract(0, total_chunks=10, total_duration=100.0)
    assert len(seg) == int(round(CHUNK_DURATION * SR))
    # Chunk 0 starts at source sample 0
    assert seg[0, 0] == 0
    assert seg[-1, 0] == int(round(CHUNK_DURATION * SR)) - 1


def test_middle_chunk_skips_overlap():
    """A middle chunk must start OVERLAP_DURATION into its buffer, not at 0."""
    chunk_index = 3
    seg = _extract(chunk_index, total_chunks=10, total_duration=100.0)

    chunk_start = chunk_index * CHUNK_INTERVAL
    expected_source_start = int(round((chunk_start + OVERLAP_DURATION) * SR))
    expected_len = int(round(CHUNK_INTERVAL * SR))

    assert len(seg) == expected_len
    assert seg[0, 0] == expected_source_start, (
        f"middle chunk {chunk_index} should start at source sample "
        f"{expected_source_start} (overlap-skipped), got {int(seg[0, 0])}"
    )
    assert seg[-1, 0] == expected_source_start + expected_len - 1


def test_middle_chunks_tile_source_gaplessly():
    """Chunk 0 + middle chunks must reconstruct a strictly +1 monotonic source ramp.

    This is the property that the old offset-0 slice violated: it re-emitted the
    5 s overlap, creating a backward jump at the chunk 0 -> 1 boundary.
    """
    total_duration = 100.0
    total_chunks = 10
    # Use chunk 0 and several middle chunks (exclude the last chunk, whose
    # trim-cap behaviour is tracked separately under BE-CP-2 / #3804).
    segments = [_extract(i, total_chunks, total_duration) for i in range(0, 6)]
    reconstructed = np.vstack(segments)[:, 0]

    diffs = np.diff(reconstructed)
    # Every step must be exactly +1 source sample: no gaps, no backward jumps.
    assert np.all(diffs == 1), (
        f"source reconstruction is not gapless/monotonic; "
        f"unique steps = {np.unique(diffs)}"
    )
    # Sanity: the chunk 0 -> 1 boundary specifically has no backward jump.
    boundary = int(round(CHUNK_DURATION * SR))
    assert reconstructed[boundary] == reconstructed[boundary - 1] + 1


def test_old_offset_zero_would_have_duplicated_overlap():
    """Guard the intent: slicing a middle buffer from offset 0 re-emits the overlap."""
    chunk_index = 1
    buf = _post_trim_buffer(chunk_index)
    interval_samples = int(round(CHUNK_INTERVAL * SR))
    overlap_samples = int(round(OVERLAP_DURATION * SR))

    old_behaviour = buf[:interval_samples]          # buggy: offset 0
    new_behaviour = _extract(chunk_index, total_chunks=10, total_duration=100.0)

    # The old slice started OVERLAP_DURATION too early.
    assert new_behaviour[0, 0] - old_behaviour[0, 0] == overlap_samples


# ---------------------------------------------------------------------------
# #4132 — rank consistency: mono 1-D input must return 2-D (N,1) on every
# validation branch (pad / trim / pass-through), not 1-D on some and 2-D on
# others.
# ---------------------------------------------------------------------------

def _extract_mono(buf_1d, chunk_index=0, total_chunks=10, total_duration=100.0):
    return ChunkOperations.extract_chunk_segment(
        processed_chunk=buf_1d,
        chunk_index=chunk_index,
        sample_rate=SR,
        chunk_duration=CHUNK_DURATION,
        chunk_interval=CHUNK_INTERVAL,
        overlap_duration=OVERLAP_DURATION,
        total_chunks=total_chunks,
        total_duration=total_duration,
    )


def test_mono_short_buffer_pads_to_2d():
    # 1 s buffer for chunk 0 (expects CHUNK_DURATION s) -> pad branch.
    seg = _extract_mono(np.arange(SR, dtype=np.float64))
    assert seg.ndim == 2
    assert seg.shape[1] == 1


def test_mono_full_buffer_passthrough_is_2d():
    # ~CHUNK_DURATION s buffer for chunk 0 -> exact / pass-through branch.
    seg = _extract_mono(np.arange(int(round(CHUNK_DURATION * SR)), dtype=np.float64))
    assert seg.ndim == 2
    assert seg.shape[1] == 1


def test_mono_pad_and_passthrough_have_same_rank():
    short = _extract_mono(np.zeros(SR, dtype=np.float64))                       # pad
    full = _extract_mono(np.zeros(int(round(CHUNK_DURATION * SR)), dtype=np.float64))  # passthrough
    assert short.ndim == full.ndim == 2


def test_stereo_input_stays_2d():
    buf = np.column_stack([np.arange(SR, dtype=np.float64)] * 2)  # (SR, 2)
    seg = _extract_mono(buf)
    assert seg.ndim == 2
    assert seg.shape[1] == 2
