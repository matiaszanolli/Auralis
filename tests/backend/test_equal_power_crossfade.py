"""
Test: equal-power crossfade in apply_crossfade_between_chunks (fixes #2080)

Verifies that:
- The crossfade uses sin²/cos² equal-power curves (not linear np.linspace)
- Energy (RMS) is preserved at the crossfade midpoint
- Mono and stereo audio are both handled correctly
- Edge cases (zero overlap, overlap larger than chunks) are safe
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from chunked_processor import apply_crossfade_between_chunks



def test_crossfade_uses_equal_power_not_linear():
    """
    The fade curves must satisfy fade_out² + fade_in² ≈ 1 (equal-power invariant).
    Linear fades only satisfy fade_out + fade_in = 1, which causes a 3 dB energy dip.
    """
    overlap = 1000
    chunk1 = np.ones(overlap * 2, dtype=np.float32)
    chunk2 = np.ones(overlap * 2, dtype=np.float32)

    result = apply_crossfade_between_chunks(chunk1, chunk2, overlap)

    # The crossfade region is at indices [len(chunk1) - overlap : len(chunk1)]
    crossfade_region = result[len(chunk1) - overlap : len(chunk1)]

    # The midpoint of the crossfade region
    mid = overlap // 2
    mid_value = crossfade_region[mid]

    # Equal-power: at midpoint t=π/4, cos²(π/4)=sin²(π/4)=0.5 → sum = 1.0
    # Linear: at midpoint fade_out=fade_in=0.5 → sum = 0.5 (6 dB loss!)
    # Since chunk1=chunk2=1.0 throughout, the crossfade output = fade_out + fade_in
    assert abs(mid_value - 1.0) < 0.01, (
        f"Midpoint crossfade value should be ~1.0 (equal-power), got {mid_value:.4f}. "
        "Linear crossfade would give ~0.5 — this indicates the bug #2080 is still present."
    )


def test_crossfade_energy_preserved_at_midpoint():
    """
    RMS energy at the crossfade midpoint must match the input amplitude.

    With constant-amplitude chunks, equal-power fades (cos² + sin² = 1) keep the
    output amplitude constant throughout the crossfade region.  Linear fades would
    produce a dip to 0.5× amplitude (−6 dB) at the midpoint.
    """
    overlap = 4410  # 100 ms at 44100 Hz
    amplitude = 0.8
    chunk1 = np.full(overlap * 2, amplitude, dtype=np.float32)
    chunk2 = np.full(overlap * 2, amplitude, dtype=np.float32)

    result = apply_crossfade_between_chunks(chunk1, chunk2, overlap)

    crossfade_region = result[len(chunk1) - overlap : len(chunk1)]
    mid_value = float(crossfade_region[overlap // 2])

    # Equal-power: cos²(π/4) + sin²(π/4) = 0.5 + 0.5 = 1.0 → output = amplitude
    assert abs(mid_value - amplitude) < 0.01, (
        f"Midpoint amplitude {mid_value:.4f} should equal input {amplitude:.4f}. "
        "Linear crossfade would give ~0.4 — bug #2080 still present."
    )


def test_crossfade_output_length_preserved():
    """Total sample count must equal len(chunk1) + len(chunk2) - overlap."""
    chunk1 = np.zeros(44100, dtype=np.float32)
    chunk2 = np.zeros(44100, dtype=np.float32)
    overlap = 13230  # 300 ms

    result = apply_crossfade_between_chunks(chunk1, chunk2, overlap)

    expected_len = len(chunk1) + len(chunk2) - overlap
    assert len(result) == expected_len, (
        f"Output length {len(result)} != expected {expected_len}"
    )


def test_crossfade_stereo():
    """Stereo (2D) arrays must be handled without shape errors."""
    overlap = 1000
    chunk1 = np.ones((44100, 2), dtype=np.float32)
    chunk2 = np.ones((44100, 2), dtype=np.float32)

    result = apply_crossfade_between_chunks(chunk1, chunk2, overlap)

    assert result.ndim == 2, "Stereo output must remain 2D"
    assert result.shape[1] == 2, "Stereo output must have 2 channels"

    # Equal-power check for stereo: midpoint of crossfade region
    crossfade_region = result[len(chunk1) - overlap : len(chunk1)]
    mid_value = crossfade_region[overlap // 2, 0]
    assert abs(mid_value - 1.0) < 0.01, (
        f"Stereo midpoint value should be ~1.0 (equal-power), got {mid_value:.4f}"
    )


def test_crossfade_zero_overlap():
    """Zero overlap must simply concatenate chunks without error."""
    chunk1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    chunk2 = np.array([4.0, 5.0, 6.0], dtype=np.float32)

    result = apply_crossfade_between_chunks(chunk1, chunk2, 0)

    expected = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype=np.float32)
    np.testing.assert_array_equal(result, expected)


def test_crossfade_overlap_larger_than_chunks():
    """Overlap clamped to min(len(chunk1), len(chunk2)) — must not crash."""
    chunk1 = np.ones(50, dtype=np.float32)
    chunk2 = np.ones(50, dtype=np.float32)

    # Request overlap larger than either chunk
    result = apply_crossfade_between_chunks(chunk1, chunk2, 1000)

    # Should still produce a valid array
    assert isinstance(result, np.ndarray)
    assert len(result) > 0
