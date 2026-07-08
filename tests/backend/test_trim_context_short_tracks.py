#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for the trim_context under-trim on short tracks (#3807 / BE-CP-2).

CONTEXT: ``ChunkBoundaryManager.trim_context()`` used a ``max_trim_fraction=0.25``
safety cap that limited the trim to 25% of the *chunk's own* buffer length. For a
short track, the last chunk's loaded (pre-DSP) buffer is itself short, so 25% of
it can be far less than the CONTEXT_DURATION (5s) trim that
``ChunkOperations.extract_chunk_segment`` assumes was fully applied. The cap
silently under-trimmed the start of the buffer, desyncing extract_chunk_segment's
fixed ``overlap_samples`` skip-offset — the final seconds of short tracks were
dropped and earlier content was duplicated in their place.

These tests exercise the REAL ``trim_context()`` (not a synthetic pre-trimmed
buffer) end-to-end with ``extract_chunk_segment()``, and assert the reconstructed
output matches the source *by content*, not just by sample count — a
length-only assertion would not have caught this bug (the dropped tail and the
duplicated content are both drop-in length matches).

:license: GPLv3
"""

import sys
from pathlib import Path

import numpy as np
import pytest

backend_path = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(backend_path))

from core.chunk_boundaries import ChunkBoundaryManager, content_chunk_count
from core.chunk_operations import ChunkOperations
from core.chunked_processor import CHUNK_DURATION, CHUNK_INTERVAL, OVERLAP_DURATION

SR = 1000  # low rate keeps arrays small; durations stay sample-exact at this rate


def _source(total_duration: float) -> np.ndarray:
    """A 2-channel ramp where each sample's value is its absolute source index."""
    total_samples = int(round(total_duration * SR))
    ramp = np.arange(total_samples, dtype=np.float64)
    return np.column_stack([ramp, ramp])


def _reconstruct_via_real_trim_context(total_duration: float) -> np.ndarray:
    """Full pipeline: load_start/load_end -> (identity DSP) -> trim_context() ->
    extract_chunk_segment(), for every chunk, concatenated.

    DSP is modeled as identity (sample-count-preserving passthrough), matching
    the CLAUDE.md invariant that processing never changes sample count — the
    real bug is entirely in the boundary/trim arithmetic, not the DSP stage.
    """
    manager = ChunkBoundaryManager(total_duration=total_duration, sample_rate=SR)
    source = _source(total_duration)
    total_chunks = manager.total_chunks

    segments = []
    for chunk_index in range(total_chunks):
        load_start, load_end, _, _ = manager.get_chunk_boundaries_samples(chunk_index)
        loaded = source[load_start:load_end]

        trimmed = manager.trim_context(loaded.copy(), chunk_index)

        extracted = ChunkOperations.extract_chunk_segment(
            processed_chunk=trimmed,
            chunk_index=chunk_index,
            sample_rate=SR,
            chunk_duration=CHUNK_DURATION,
            chunk_interval=CHUNK_INTERVAL,
            overlap_duration=OVERLAP_DURATION,
            total_chunks=total_chunks,
            total_duration=total_duration,
        )
        segments.append(extracted)

    return np.vstack(segments)[:, 0]


# --- single-chunk short tracks (total_duration < 15s) ------------------------

@pytest.mark.parametrize("duration", [1.0, 5.0, 9.0, 12.0, 14.9])
def test_single_chunk_short_track_matches_source_exactly(duration):
    """A track short enough for exactly 1 chunk must reproduce the source
    byte-for-byte — chunk 0 has no start trim and (being the only/last chunk)
    no end trim, so this path doesn't exercise the cap, but anchors the
    baseline before the 2-chunk cases below."""
    assert content_chunk_count(duration) == 1

    recon = _reconstruct_via_real_trim_context(duration)
    expected = np.arange(int(round(duration * SR)), dtype=np.float64)

    assert len(recon) == len(expected)
    np.testing.assert_array_equal(recon, expected)


# --- 2-chunk short tracks (15s < total_duration < 25s): the actual bug -------

@pytest.mark.parametrize("duration", [15.1, 17.0, 18.5, 20.0, 22.0, 24.9])
def test_two_chunk_short_track_matches_source_by_content(duration):
    """The headline regression: a short 2-chunk track's last chunk has a short
    loaded buffer, which used to trip the max_trim_fraction cap. Assert
    CONTENT equality (not just length) — a dropped tail with duplicated
    earlier content can coincidentally match the source's total length.
    """
    assert content_chunk_count(duration) == 2

    recon = _reconstruct_via_real_trim_context(duration)
    expected = np.arange(int(round(duration * SR)), dtype=np.float64)

    assert len(recon) == len(expected), (
        f"duration {duration}s: emitted {len(recon)} samples, "
        f"expected {len(expected)}"
    )
    # Gapless, strictly-increasing source reconstruction: no gaps (dropped
    # content), no backward jumps or repeats (duplicated content).
    assert np.all(np.diff(recon) == 1), (
        f"duration {duration}s: reconstruction is not a gapless +1 ramp — "
        f"content was dropped and/or duplicated"
    )
    np.testing.assert_array_equal(recon, expected)


def test_two_chunk_short_track_last_chunk_end_matches_source_tail():
    """Explicit regression for the exact failure mode described in #3807: the
    final seconds of a short track must be present in the output, not lost."""
    duration = 18.5
    recon = _reconstruct_via_real_trim_context(duration)
    expected_tail = np.arange(
        int(round(duration * SR)) - 100, int(round(duration * SR)), dtype=np.float64
    )
    np.testing.assert_array_equal(recon[-100:], expected_tail)


# --- trim_context() unit-level: the cap no longer under-trims ---------------

def test_trim_context_applies_full_start_trim_on_short_last_chunk(caplog):
    """Unit-level check on trim_context() itself: for a short last chunk whose
    loaded buffer would have tripped the old 25%-of-length cap, the full
    CONTEXT_DURATION start-trim must still be applied."""
    duration = 18.5
    manager = ChunkBoundaryManager(total_duration=duration, sample_rate=SR)
    assert manager.total_chunks == 2

    chunk_index = 1
    load_start, load_end, _, _ = manager.get_chunk_boundaries_samples(chunk_index)
    loaded_length = load_end - load_start
    context_samples = round(5.0 * SR)  # CONTEXT_DURATION

    # Sanity: this scenario actually exercises the old cap (25% of a buffer
    # shorter than 4x the context amount would have under-trimmed).
    assert loaded_length < 4 * context_samples

    buffer = np.zeros((loaded_length, 2))
    with caplog.at_level("WARNING"):
        trimmed = manager.trim_context(buffer, chunk_index)

    assert len(trimmed) == loaded_length - context_samples
    assert "clamped to avoid emptying the buffer" not in caplog.text
