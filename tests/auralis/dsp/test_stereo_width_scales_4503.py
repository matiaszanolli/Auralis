"""
Stereo width scale hygiene and multiband behaviour (#4503, #4504, #4505)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Three "width" scales coexist in this codebase and are not interchangeable:

1. decorrelation  -- ``stereo_width_analysis``: ``1 - |corr(L,R)|``, 0 = mono
2. width factor   -- ``adjust_stereo_width`` argument: ``side_gain = 2 * factor``,
                     so 0.5 = unchanged
3. side-energy    -- the ``stereo_width`` fingerprint dimension

Scales 1 and 2 both live in 0..1 with 0.5 near the middle, which is exactly why
comparing them looked reasonable and was wrong. The processors used to ask
"would this widen?" by testing ``target_width > current_width`` — an
instruction against a measurement.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.dsp.utils.stereo import (
    WIDTH_FACTOR_UNITY,
    adjust_stereo_width,
    adjust_stereo_width_multiband,
    stereo_width_analysis,
)

SR = 44100


def _decorrelated(n: int = SR * 2, seed: int = 0, amp: float = 0.1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.stack(
        [rng.standard_normal(n), rng.standard_normal(n)], axis=1
    ).astype(np.float32) * amp


def _side(audio: np.ndarray) -> np.ndarray:
    return (audio[:, 0] - audio[:, 1]) / 2.0


def _band_side_gain(before: np.ndarray, after: np.ndarray, lo: float, hi: float) -> float:
    """RMS side-signal gain within [lo, hi) Hz."""
    n = before.shape[0]
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    mask = (freqs >= lo) & (freqs < hi)
    e0 = np.sum(np.abs(np.fft.rfft(_side(before))[mask]) ** 2)
    e1 = np.sum(np.abs(np.fft.rfft(_side(after))[mask]) ** 2)
    return float(np.sqrt(e1 / e0)) if e0 > 0 else float("nan")


# ---------------------------------------------------------------------------
# #4503 — the two axes
# ---------------------------------------------------------------------------

class TestWidthFactorAxis:
    def test_unity_constant_is_the_no_op_point(self):
        audio = _decorrelated()
        out = adjust_stereo_width(audio, WIDTH_FACTOR_UNITY)
        np.testing.assert_allclose(out, audio, rtol=1e-6, atol=1e-7)

    @pytest.mark.parametrize("factor", [0.55, 0.7, 0.9, 1.0])
    def test_above_unity_always_widens(self, factor: float):
        """Acceptance criterion: above-unity maps to widening, never narrowing."""
        audio = _decorrelated()
        out = adjust_stereo_width(audio, factor)
        gain = np.std(_side(out)) / np.std(_side(audio))
        assert gain > 1.0, f"factor {factor} narrowed instead of widening"
        assert gain == pytest.approx(factor / WIDTH_FACTOR_UNITY, rel=1e-4)

    @pytest.mark.parametrize("factor", [0.45, 0.3, 0.1, 0.0])
    def test_below_unity_always_narrows(self, factor: float):
        audio = _decorrelated()
        out = adjust_stereo_width(audio, factor)
        gain = np.std(_side(out)) / np.std(_side(audio))
        assert gain < 1.0, f"factor {factor} widened instead of narrowing"

    def test_widen_direction_is_independent_of_input_decorrelation(self):
        """The bug: direction used to depend on the measured decorrelation.

        A near-mono source and a fully decorrelated source given the SAME
        above-unity width factor must both widen. Under the old comparison the
        decorrelation reading decided whether the request even ran.
        """
        near_mono = _decorrelated(seed=1)
        near_mono[:, 1] = near_mono[:, 0] * 0.98  # highly correlated
        decorrelated = _decorrelated(seed=2)

        assert stereo_width_analysis(near_mono) < 0.2
        assert stereo_width_analysis(decorrelated) > 0.8

        for audio in (near_mono, decorrelated):
            out = adjust_stereo_width(audio, 0.75)
            gain = np.std(_side(out)) / np.std(_side(audio))
            assert gain == pytest.approx(1.5, rel=1e-3)

    def test_the_two_scales_disagree_by_construction(self):
        """Pin WHY they must not be compared, so the guard is not 'simplified'.

        Untouched audio always sits at unity (0.5) on the width-factor axis, but
        its decorrelation reading can be anything in 0..1. Any comparison
        between them is therefore a function of the material, not of the intent.
        """
        near_mono = _decorrelated(seed=3)
        near_mono[:, 1] = near_mono[:, 0] * 0.99
        decorrelated = _decorrelated(seed=4)

        readings = [stereo_width_analysis(near_mono), stereo_width_analysis(decorrelated)]
        assert min(readings) < WIDTH_FACTOR_UNITY < max(readings), (
            "expected the decorrelation reading to straddle the unity width "
            "factor — that straddle is what made the old comparison flip"
        )


# ---------------------------------------------------------------------------
# #4504 — low frequencies are protected
# ---------------------------------------------------------------------------

class TestLowFrequencyProtection:
    def test_bass_fundamentals_are_not_widened(self):
        audio = _decorrelated(n=SR * 4, seed=5)
        out = adjust_stereo_width_multiband(audio, 1.0, SR)
        for lo, hi in [(20, 50), (50, 80), (80, 120)]:
            gain = _band_side_gain(audio, out, lo, hi)
            assert gain == pytest.approx(1.0, abs=0.02), (
                f"{lo}-{hi} Hz side gain {gain:.3f}: bass should stay centred"
            )

    def test_highs_are_widened(self):
        audio = _decorrelated(n=SR * 4, seed=6)
        out = adjust_stereo_width_multiband(audio, 1.0, SR)
        assert _band_side_gain(audio, out, 8000, 16000) > 1.5

    def test_full_band_by_contrast_widens_the_bass(self):
        """Why multiband matters: the full-band path has no low-end protection."""
        audio = _decorrelated(n=SR * 4, seed=7)
        out = adjust_stereo_width(audio, 1.0)
        assert _band_side_gain(audio, out, 20, 120) == pytest.approx(2.0, rel=0.02)

    def test_transition_region_is_partially_widened_not_brick_walled(self):
        """Documented reality (#4504): the 120-300 Hz skirt leaks, mildly.

        The docstring says "no expansion below 300 Hz"; the order-2 extraction
        filter makes that a taper, not a wall. Pinned so the claim in the
        docstring stays honest.
        """
        audio = _decorrelated(n=SR * 4, seed=8)
        out = adjust_stereo_width_multiband(audio, 1.0, SR)
        gain = _band_side_gain(audio, out, 250, 300)
        assert 1.05 < gain < 1.35, f"250-300 Hz side gain {gain:.3f} outside the measured taper"


# ---------------------------------------------------------------------------
# #4505 — crossover behaviour
# ---------------------------------------------------------------------------

class TestCrossoverResponse:
    def test_no_width_bump_at_the_2khz_seam(self):
        """The 2 kHz response must be monotonic — widened once, not twice.

        The shared 2 kHz edge is CORRECT: an order-2 Butterworth under
        sosfiltfilt sits at ~0.5 amplitude at its cutoff, so the two bandpasses
        are amplitude-complementary there. Splitting the edge apart would open a
        hole. This test fails either way — bump or hole — so it guards both.
        """
        audio = _decorrelated(n=SR * 8, seed=9)
        out = adjust_stereo_width_multiband(audio, 1.0, SR)

        edges = list(range(1500, 2700, 100))
        gains = [_band_side_gain(audio, out, lo, lo + 100) for lo in edges[:-1]]

        for lo, a, b in zip(edges, gains, gains[1:]):
            assert b >= a - 0.01, (
                f"width response dips at {lo}->{lo+100} Hz ({a:.3f} -> {b:.3f})"
            )
        # And no local spike relative to the surrounding trend.
        span = gains[-1] - gains[0]
        for i in range(1, len(gains) - 1):
            local = gains[i] - gains[i - 1]
            assert local < span, f"width spike near {edges[i]} Hz"

    def test_response_rises_smoothly_with_frequency(self):
        """Design intent: more widening with increasing frequency."""
        audio = _decorrelated(n=SR * 8, seed=10)
        out = adjust_stereo_width_multiband(audio, 1.0, SR)
        bands = [(400, 800), (800, 1600), (1600, 3200), (3200, 6400)]
        gains = [_band_side_gain(audio, out, lo, hi) for lo, hi in bands]
        assert gains == sorted(gains), f"expected a rising width ramp, got {gains}"


class TestInvariants:
    @pytest.mark.parametrize("factor", [0.0, 0.3, 0.5, 0.75, 1.0])
    def test_sample_count_and_dtype_preserved(self, factor: float):
        audio = _decorrelated(n=SR, seed=11)
        for fn in (
            lambda a: adjust_stereo_width(a, factor),
            lambda a: adjust_stereo_width_multiband(a, factor, SR),
        ):
            out = fn(audio)
            assert out.shape == audio.shape
            assert out.dtype == audio.dtype
            assert np.all(np.isfinite(out))

    def test_input_is_not_mutated(self):
        audio = _decorrelated(n=SR, seed=12)
        original = audio.copy()
        adjust_stereo_width(audio, 0.9)
        adjust_stereo_width_multiband(audio, 0.9, SR)
        np.testing.assert_array_equal(audio, original)

    def test_mono_input_passes_through(self):
        # A pass-through/no-op branch must still return a copy, never the
        # caller's own array object (#4900) — equal in value, not identity.
        mono = np.zeros((1000, 1), dtype=np.float32)
        result_a = adjust_stereo_width(mono, 0.9)
        assert result_a is not mono
        np.testing.assert_array_equal(result_a, mono)

        result_b = adjust_stereo_width_multiband(mono, 0.9, SR)
        assert result_b is not mono
        np.testing.assert_array_equal(result_b, mono)
