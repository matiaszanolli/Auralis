"""
Test: equal-gain crossfade in apply_crossfade_between_chunks (fixes #2080)

`apply_crossfade_between_chunks` (core/chunk_crossfade.py) uses sin²/cos²
fade curves — equal-GAIN (amplitude-complementary: fade_out + fade_in = 1),
not equal-POWER (fade_out² + fade_in² = 1, which needs bare sin/cos without
the square). #3878 corrected the function's own docstring/comment, which had
claimed "equal-power" for years; this test file inherited the same wrong
name and was rewritten alongside that fix.

#3878 also flagged this file's original assertions as VACUOUS: checking only
`fade_out + fade_in ≈ 1` at the midpoint cannot distinguish sin²/cos² from a
naive linear ramp (fade_out=1-t, fade_in=t) — complementary linear ramps sum
to 1 at every point too, not just cos²(t)+sin²(t)=1's Pythagorean identity.
The old comment claiming "Linear: at midpoint fade_out=fade_in=0.5 → sum =
0.5" was itself arithmetically wrong (0.5+0.5=1.0, not 0.5) — this is why the
test passed identically whether the curve was linear, sin²/cos², or true
equal-power. `test_crossfade_curve_shape_is_not_linear` below is the fix:
it samples off-midpoint, where sin²/cos² and a linear ramp actually diverge.

Verifies that:
- The fade curve shape is genuinely sin²/cos² (not a linear ramp in disguise)
- fade_out + fade_in ≈ 1 throughout (equal-gain, NOT equal-power — a switch
  to true equal-power, i.e. bare sin/cos, would push the midpoint to ~1.414x
  and fail these same assertions)
- Energy (RMS) is preserved at the crossfade midpoint
- Mono and stereo audio are both handled correctly
- Edge cases (zero overlap, overlap larger than chunks) are safe
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunked_processor import apply_crossfade_between_chunks



def test_crossfade_curve_shape_is_not_linear():
    """
    Discriminates sin²/cos² from a naive linear ramp (fixes #3878's vacuous-
    test finding). Complementary linear ramps sum to 1 at every point, same
    as sin²/cos² — so a midpoint-only sum check can't tell them apart. This
    samples a quarter of the way through the overlap, where the two curves
    diverge: cos²(π/8) ≈ 0.8536 vs a linear ramp's 0.75.
    """
    overlap = 1000
    chunk1 = np.ones(overlap * 2, dtype=np.float32)
    chunk2 = np.zeros(overlap * 2, dtype=np.float32)

    result = apply_crossfade_between_chunks(chunk1, chunk2, overlap)
    crossfade_region = result[len(chunk1) - overlap : len(chunk1)]

    # chunk2 is silent, so crossfade_region == fade_out(chunk1) alone —
    # isolates the curve shape directly instead of a chunk1+chunk2 sum.
    quarter_idx = overlap // 4
    quarter_value = float(crossfade_region[quarter_idx])

    expected_cos_sq = float(np.cos(np.pi / 8) ** 2)  # ≈ 0.8536
    linear_equivalent = 0.75

    assert abs(quarter_value - expected_cos_sq) < 0.01, (
        f"fade_out at 25% through the overlap should be cos²(π/8) ≈ "
        f"{expected_cos_sq:.4f} (equal-gain curve), got {quarter_value:.4f}. "
        f"A linear ramp would give {linear_equivalent} instead."
    )
    assert abs(quarter_value - linear_equivalent) > 0.05, (
        "fade_out at 25% matches a LINEAR ramp's value, not the cos² curve — "
        "the crossfade may have regressed to a naive linspace fade (#2080)."
    )


def test_crossfade_is_equal_gain_not_true_equal_power():
    """
    The fade curves satisfy fade_out + fade_in ≈ 1 (equal-GAIN invariant) —
    correct for crossfading correlated content (adjacent chunks of the same
    track). True equal-power (fade_out² + fade_in² ≈ 1, via bare sin/cos)
    would instead push the midpoint to ~1.414x for constant-amplitude
    input — do NOT "fix" this test to expect that value; see #3878.
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

    # Equal-gain: at midpoint t=π/4, cos²(π/4)=sin²(π/4)=0.5 → sum = 1.0
    # True equal-power (bare cos/sin): cos(π/4)+sin(π/4) ≈ 1.414 (a ~+3dB
    # bulge for this correlated, constant-amplitude input — wrong here).
    # Since chunk1=chunk2=1.0 throughout, the crossfade output = fade_out + fade_in
    assert abs(mid_value - 1.0) < 0.01, (
        f"Midpoint crossfade value should be ~1.0 (equal-gain), got {mid_value:.4f}. "
        "~1.414 would mean this regressed to true equal-power (sin/cos, no square) — "
        "wrong for this correlated-chunk use case (#3878)."
    )


def test_crossfade_energy_preserved_at_midpoint():
    """
    RMS energy at the crossfade midpoint must match the input amplitude.

    With constant-amplitude chunks, equal-gain fades (cos² + sin² = 1) keep the
    output amplitude constant throughout the crossfade region.
    """
    overlap = 4410  # 100 ms at 44100 Hz
    amplitude = 0.8
    chunk1 = np.full(overlap * 2, amplitude, dtype=np.float32)
    chunk2 = np.full(overlap * 2, amplitude, dtype=np.float32)

    result = apply_crossfade_between_chunks(chunk1, chunk2, overlap)

    crossfade_region = result[len(chunk1) - overlap : len(chunk1)]
    mid_value = float(crossfade_region[overlap // 2])

    # Equal-gain: cos²(π/4) + sin²(π/4) = 0.5 + 0.5 = 1.0 → output = amplitude
    assert abs(mid_value - amplitude) < 0.01, (
        f"Midpoint amplitude {mid_value:.4f} should equal input {amplitude:.4f}."
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

    # Equal-gain check for stereo: midpoint of crossfade region
    crossfade_region = result[len(chunk1) - overlap : len(chunk1)]
    mid_value = crossfade_region[overlap // 2, 0]
    assert abs(mid_value - 1.0) < 0.01, (
        f"Stereo midpoint value should be ~1.0 (equal-gain), got {mid_value:.4f}"
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
