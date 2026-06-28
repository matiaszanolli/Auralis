#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for chunk-count over-allocation (#4124).

CONTEXT: ``total_chunks = ceil(total_duration / CHUNK_INTERVAL)`` over-allocated
a trailing chunk for any duration in ``(n*INTERVAL, n*INTERVAL + OVERLAP)``. That
extra chunk emits 0 samples of *new* content, so the real penultimate chunk falls
into the regular branch (which expects a full CHUNK_INTERVAL of new content),
comes up short, and gets padded with silence — appending up to OVERLAP seconds of
trailing silence and caching a 0-sample WAV. A Monte-Carlo sweep over 15-360 s
showed ~49 % of durations affected (e.g. a 21 s track emitted 25 s).

``content_chunk_count`` now counts only chunks that carry new content, so the
penultimate chunk is correctly the last chunk and no silence is padded.

These tests model the IDEAL (non-capped) context trim — the ``max_trim_fraction``
cap on very short final buffers is a separate concern (BE-CP-2 / #3807).

:license: GPLv3
"""

import sys
from pathlib import Path

import numpy as np
import pytest

backend_path = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(backend_path))

from core.chunk_boundaries import content_chunk_count
from core.chunk_operations import ChunkOperations
from core.chunked_processor import CHUNK_DURATION, CHUNK_INTERVAL, OVERLAP_DURATION

SR = 1000  # low rate keeps arrays small; durations stay sample-exact at this rate


def _trimmed_buffer(chunk_index: int, total_chunks: int, total_duration: float,
                    channels: int = 2) -> np.ndarray:
    """Context-trimmed buffer handed to extract_chunk_segment.

    Each sample's value is its absolute source sample index, so a concatenation
    of the emitted segments can be checked for gaplessness directly. The buffer
    spans source time ``[chunk_start, min(chunk_start + CHUNK_DURATION, total)]``
    — the load is always capped at the file end, which is exactly what produces a
    short penultimate buffer when the chunk count is over-allocated.
    """
    chunk_start_s = chunk_index * CHUNK_INTERVAL  # 0 for chunk 0
    start_idx = int(round(chunk_start_s * SR))
    total_samples = int(round(total_duration * SR))
    end_idx = min(int(round((chunk_start_s + CHUNK_DURATION) * SR)), total_samples)
    ramp = np.arange(start_idx, end_idx, dtype=np.float64)
    return np.column_stack([ramp] * channels)


def _extract(chunk_index: int, total_chunks: int, total_duration: float) -> np.ndarray:
    return ChunkOperations.extract_chunk_segment(
        processed_chunk=_trimmed_buffer(chunk_index, total_chunks, total_duration),
        chunk_index=chunk_index,
        sample_rate=SR,
        chunk_duration=CHUNK_DURATION,
        chunk_interval=CHUNK_INTERVAL,
        overlap_duration=OVERLAP_DURATION,
        total_chunks=total_chunks,
        total_duration=total_duration,
    )


def _reconstruct(total_duration: float) -> np.ndarray:
    """Emit every chunk for ``total_duration`` and concatenate the source ramp."""
    total_chunks = content_chunk_count(total_duration)
    segments = [_extract(i, total_chunks, total_duration) for i in range(total_chunks)]
    return np.vstack(segments)[:, 0]


# --- content_chunk_count: no spurious chunk, no under-allocation -------------

def test_content_chunk_count_21s_is_two_not_three():
    """The headline regression: a 21 s track must allocate 2 chunks, not 3."""
    assert content_chunk_count(21.0) == 2


@pytest.mark.parametrize("duration", [0.0, 1.0, 5.0, 10.0, 14.9, 15.0])
def test_content_chunk_count_short_tracks_single_chunk(duration):
    assert content_chunk_count(duration) == 1


@pytest.mark.parametrize(
    "n",
    list(range(2, 37)),  # n*10 = 20..360 s
)
@pytest.mark.parametrize("frac", [0.001, 2.5, 5.0, 7.5, 9.999])
def test_content_chunk_count_is_minimal_and_sufficient(n, frac):
    """For every duration: the allocated count covers it, but one fewer would not.

    Coverage after ``k`` chunks (k >= 1) is ``CHUNK_DURATION + (k-1)*INTERVAL``
    (chunk 0 emits CHUNK_DURATION; each later chunk emits INTERVAL).
    """
    duration = n * 10 + frac
    count = content_chunk_count(duration)

    coverage = lambda k: CHUNK_DURATION + (k - 1) * CHUNK_INTERVAL  # noqa: E731
    # Sufficient: the allocated chunks reach the end.
    assert coverage(count) >= duration - 1e-9
    # Minimal: one fewer chunk would leave content uncovered (no spurious chunk).
    assert coverage(count - 1) < duration


# --- end-to-end: correct sample count, gapless, no silence padding ----------

def test_21s_emits_21s_not_25s_and_no_padding(caplog):
    duration = 21.0
    with caplog.at_level("WARNING"):
        recon = _reconstruct(duration)

    assert len(recon) == int(round(duration * SR))  # 21 s, not 25 s
    assert recon[0] == 0
    assert recon[-1] == int(round(duration * SR)) - 1
    # Strictly +1 source ramp ⇒ no gaps, no backward jumps, no silence inserted.
    assert np.all(np.diff(recon) == 1)
    assert "padded with silence" not in caplog.text


@pytest.mark.parametrize(
    "duration",
    [n * 10 + frac
     for n in range(2, 19)          # 20..180 s base
     for frac in (0.0, 2.5, 5.0, 7.5)],
)
def test_sweep_total_samples_preserved_no_padding(duration, caplog):
    """Across the previously-affected band, emitted samples == source samples."""
    with caplog.at_level("WARNING"):
        recon = _reconstruct(duration)

    expected_samples = int(round(duration * SR))
    assert len(recon) == expected_samples, (
        f"duration {duration}s: emitted {len(recon)} samples, "
        f"expected {expected_samples}"
    )
    # Gapless, monotonic source reconstruction (no silence, no overshoot).
    assert recon[0] == 0
    assert recon[-1] == expected_samples - 1
    assert np.all(np.diff(recon) == 1)
    assert "padded with silence" not in caplog.text


def test_no_zero_sample_trailing_chunk():
    """No allocated chunk emits 0 samples for the previously-affected band."""
    for n in range(2, 19):
        for frac in (0.001, 2.5, 5.0, 7.5, 9.999):
            duration = n * 10 + frac
            total_chunks = content_chunk_count(duration)
            for i in range(total_chunks):
                seg = _extract(i, total_chunks, duration)
                assert len(seg) > 0, (
                    f"duration {duration}s chunk {i}/{total_chunks} emitted "
                    f"0 samples (spurious trailing chunk)"
                )
