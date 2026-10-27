"""
Regression: the stereo_expansion width curve has no jumps (#5724)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The three branches of `narrowness_factor` did not meet: at width 0.15 the first
ended at 0.6 while the Gaussian started at 0.195; at 0.30 the Gaussian ended at
0.195 and the fade started at 0.3. Tracks 0.0002 apart in measured width got a
side gain of +2.6 dB vs +0.9 dB.
"""

import numpy as np
import pytest

from auralis.core.stages import stereo_expansion
from auralis.core.stages.stereo_expansion import narrowness_curve


def _stereo(seconds: float = 1.0, sr: int = 44100) -> np.ndarray:
    rng = np.random.default_rng(0)
    mid = rng.standard_normal(int(sr * seconds)) * 0.1
    return np.stack([mid, mid + rng.standard_normal(mid.size) * 0.01])


class TestContinuity:
    @pytest.mark.parametrize("edge", [0.15, 0.30])
    def test_no_jump_across_a_branch_boundary(self, edge):
        below, above = narrowness_curve(edge - 0.0001), narrowness_curve(edge + 0.0001)
        assert abs(above - below) < 0.005

    def test_sweep_has_no_step(self):
        widths = np.arange(0.0, 0.40, 0.0005)
        values = np.array([narrowness_curve(w) for w in widths])
        assert np.abs(np.diff(values)).max() < 0.01

    def test_edge_values_are_exact(self):
        assert narrowness_curve(0.15) == pytest.approx(0.6)
        assert narrowness_curve(0.30) == pytest.approx(0.3)
        assert narrowness_curve(0.0) == pytest.approx(1.0)


class TestAnchorsPreserved:
    def test_narrowest_material_is_widened_most(self):
        assert narrowness_curve(0.0) > narrowness_curve(0.10) > narrowness_curve(0.15 - 1e-9)

    def test_bell_keeps_its_value_at_the_old_centre(self):
        assert narrowness_curve(0.225) == pytest.approx(0.6)

    def test_bell_matches_the_old_curve_on_the_falling_side(self):
        old = 0.6 * np.exp(-((0.25 - 0.225) ** 2) / (2 * 0.05**2))
        assert narrowness_curve(0.25) == pytest.approx(old, abs=0.02)

    def test_fades_to_zero_at_the_upper_edge(self):
        assert narrowness_curve(0.3999) == pytest.approx(0.0, abs=1e-3)
        assert narrowness_curve(0.35) == pytest.approx(0.15, abs=0.01)

    def test_always_within_unit_range(self):
        values = [narrowness_curve(w) for w in np.arange(0.0, 0.40, 0.001)]
        assert min(values) >= 0.0 and max(values) <= 1.0


class TestApply:
    def _extra_width(self, width: float) -> float:
        _, info = stereo_expansion.apply(_stereo(), width, 1.0, 44100, False)
        return 0.0 if info is None else info['width_factor'] - 0.5

    @pytest.mark.parametrize("edge", [0.15, 0.30])
    def test_neighbouring_widths_get_neighbouring_expansion(self, edge):
        """Probe from the issue: 0.1499 -> 0.078 vs 0.1501 -> 0.025 before."""
        assert abs(self._extra_width(edge + 0.0001) - self._extra_width(edge - 0.0001)) < 0.005

    def test_width_at_or_beyond_the_ceiling_is_untouched(self):
        audio = _stereo()
        out, info = stereo_expansion.apply(audio, 0.40, 1.0, 44100, False)
        assert info is None
        assert np.array_equal(out, audio)
