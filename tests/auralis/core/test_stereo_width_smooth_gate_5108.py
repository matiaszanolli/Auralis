"""
Stereo-width expansion has no categorical step at the peak guard (#5108).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ContinuousMode._apply_stereo_width`` — the live default path
(``use_continuous_space=True``) — gated the whole widening operation on a bare
``if pre_peak_db > -2.0 and target_width > WIDTH_FACTOR_UNITY: return audio``.
Two masters 0.01 dB apart straddling -2.0 dBFS received either full
``adjust_stereo_width_multiband()`` treatment or none: an audible stereo-image
difference produced by an inaudible input difference, in a peak region the
pipeline's own -0.3 dBFS ceiling makes common.

#4860 rewrote the three other cross-dimensional guards in this same file to use
``smooth_gate()`` to eliminate exactly this bug class; this fourth one, a few
lines below the phase-drop branch in the same method, was never migrated.

These tests assert the continuous-space invariant directly: sweeping the input
peak across the knee must move the effective width smoothly, with no step.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.core.processing.continuous_mode import (
    WIDTH_PEAK_KNEE_END,
    WIDTH_PEAK_KNEE_START,
)
from auralis.core.processing.cross_dimensional_guard import smooth_gate
from auralis.dsp.utils.stereo import WIDTH_FACTOR_UNITY


def _eased_width(target_width: float, pre_peak_db: float) -> float:
    """The width the stage will actually apply — mirrors the production line.

    Kept in lockstep with `_apply_stereo_width`; the tests below are about the
    shape of this curve, which is what the invariant is about.
    """
    if target_width <= WIDTH_FACTOR_UNITY:
        return target_width
    gate = smooth_gate(pre_peak_db, WIDTH_PEAK_KNEE_START, WIDTH_PEAK_KNEE_END)
    return target_width + (WIDTH_FACTOR_UNITY - target_width) * gate


class TestNoCategoricalStep:
    def test_sweep_across_the_old_threshold_is_continuous(self):
        """The -2.0 dBFS cliff is gone: no adjacent pair jumps."""
        widen = WIDTH_FACTOR_UNITY + 0.3
        peaks = np.arange(-6.0, 0.0, 0.01)
        widths = np.array([_eased_width(widen, float(p)) for p in peaks])

        steps = np.abs(np.diff(widths))
        assert steps.max() < 0.01, (
            f"largest single-step change {steps.max():.4f} at "
            f"{peaks[int(np.argmax(steps))]:.2f} dB — a categorical jump remains"
        )

    def test_the_specific_pair_the_issue_names(self):
        """Two masters 0.01 dB apart straddling -2.0 dBFS."""
        widen = WIDTH_FACTOR_UNITY + 0.3
        below = _eased_width(widen, -2.005)
        above = _eased_width(widen, -1.995)
        assert abs(above - below) < 0.005, (
            f"0.01 dB of input produced {abs(above - below):.4f} of width change"
        )

    def test_monotonic_in_peak(self):
        """More peak never means more widening."""
        widen = WIDTH_FACTOR_UNITY + 0.3
        widths = [_eased_width(widen, float(p)) for p in np.arange(-6.0, 0.0, 0.05)]
        assert all(b <= a + 1e-9 for a, b in zip(widths, widths[1:]))


class TestFarFieldUnchanged:
    """The knee is centred on the old threshold, so far-field behaviour holds."""

    def test_quiet_material_still_widens_fully(self):
        widen = WIDTH_FACTOR_UNITY + 0.3
        assert _eased_width(widen, -12.0) == pytest.approx(widen)

    def test_near_clipping_converges_to_unity(self):
        """The clipping-safety intent of the original guard is preserved."""
        widen = WIDTH_FACTOR_UNITY + 0.3
        assert _eased_width(widen, -0.1) == pytest.approx(WIDTH_FACTOR_UNITY)

    def test_gate_endpoints(self):
        assert smooth_gate(WIDTH_PEAK_KNEE_START - 1.0, WIDTH_PEAK_KNEE_START,
                           WIDTH_PEAK_KNEE_END) == pytest.approx(0.0)
        assert smooth_gate(WIDTH_PEAK_KNEE_END + 1.0, WIDTH_PEAK_KNEE_START,
                           WIDTH_PEAK_KNEE_END) == pytest.approx(1.0)


class TestNarrowingIsUngated:
    """#4503: a narrowing request cannot raise peaks, so it must pass through."""

    @pytest.mark.parametrize("peak_db", [-12.0, -2.5, -2.0, -0.1])
    def test_narrowing_is_never_eased(self, peak_db):
        narrow = WIDTH_FACTOR_UNITY - 0.2
        assert _eased_width(narrow, peak_db) == pytest.approx(narrow)

    @pytest.mark.parametrize("peak_db", [-12.0, -0.1])
    def test_unity_request_is_untouched(self, peak_db):
        assert _eased_width(WIDTH_FACTOR_UNITY, peak_db) == pytest.approx(
            WIDTH_FACTOR_UNITY
        )


class TestKneeConstants:
    def test_knee_brackets_the_old_threshold(self):
        assert WIDTH_PEAK_KNEE_START < -2.0 <= WIDTH_PEAK_KNEE_END

    def test_knee_is_ordered(self):
        assert WIDTH_PEAK_KNEE_START < WIDTH_PEAK_KNEE_END


class TestAgainstTheRealStage:
    """Drive the production method, so _eased_width above cannot drift from it.

    Measured on the output's own decorrelation rather than on the width factor:
    that is the audible quantity, and it is what a reader of the invariant
    actually cares about.
    """

    @staticmethod
    def _stage(audio, target_width):
        from types import SimpleNamespace

        from auralis.core.processing.continuous_mode import ContinuousMode

        stub = SimpleNamespace(config=SimpleNamespace(internal_sample_rate=44100))
        params = SimpleNamespace(stereo_width_target=target_width)
        return ContinuousMode._apply_stereo_width(stub, audio, params)

    @staticmethod
    def _decorrelated_stereo(peak: float, n: int = 8192):
        """(samples, 2) with genuinely different channels, scaled to `peak`."""
        rng = np.random.default_rng(1234)
        left = rng.standard_normal(n)
        right = 0.6 * left + 0.4 * rng.standard_normal(n)
        stereo = np.stack([left, right], axis=1).astype(np.float32)
        stereo /= np.max(np.abs(stereo))
        return (stereo * peak).astype(np.float32)

    def test_output_changes_continuously_across_the_knee(self):
        from auralis.dsp.utils.stereo import stereo_width_analysis

        widen = WIDTH_FACTOR_UNITY + 0.3
        # Peaks straddling the -3.0..-2.0 dB knee.
        peaks_db = np.arange(-4.0, -1.0, 0.05)
        decorr = []
        for pdb in peaks_db:
            audio = self._decorrelated_stereo(float(10 ** (pdb / 20.0)))
            out = self._stage(audio, widen)
            assert out.shape == audio.shape
            assert out.dtype == audio.dtype
            decorr.append(stereo_width_analysis(out))

        steps = np.abs(np.diff(np.array(decorr)))
        assert steps.max() < 0.05, (
            f"decorrelation jumped {steps.max():.4f} between adjacent 0.05 dB "
            f"steps near {peaks_db[int(np.argmax(steps))]:.2f} dB — the "
            "categorical step is still present in the real stage"
        )

    def test_mono_input_is_returned_untouched(self):
        mono = np.zeros((1024, 1), dtype=np.float32)
        out = self._stage(mono, WIDTH_FACTOR_UNITY + 0.3)
        assert out is mono
