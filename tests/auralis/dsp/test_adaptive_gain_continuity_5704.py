"""
Regression: adaptive makeup gain is a continuous function (#5704)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``calculate_adaptive_gain`` was a lookup over three LUFS buckets and three crest
buckets: inputs 0.02 apart on a threshold (-12.01 vs -11.99 LUFS, 11.99 vs
12.01 dB crest) got up to 1.5 dB different makeup gain. Its bass/transient
reduction sat behind a test that was always true for the only branch that
reached it, so no input ever changed the result; it is removed.
"""

import inspect

import numpy as np
import pytest

from auralis.dsp.utils.adaptive_loudness import AdaptiveLoudnessControl as ALC

gain = lambda *a, **k: ALC.calculate_adaptive_gain(*a, **k)[0]  # noqa: E731


def _max_step(values) -> float:
    return float(np.max(np.abs(np.diff(values))))


class TestContinuity:
    @pytest.mark.parametrize("crest", [None, 10.0, 13.5, 17.0])
    @pytest.mark.parametrize("intensity", [0.3, 0.5, 1.0])
    def test_no_step_across_the_loudness_thresholds(self, crest, intensity):
        lufs = np.arange(-30.0, -8.0, 0.01)

        gains = [gain(l, intensity, crest) for l in lufs]

        assert _max_step(gains) < 0.2

    @pytest.mark.parametrize("lufs", [-13.0, -18.0, -25.0])
    def test_no_step_across_the_crest_thresholds(self, lufs):
        crest = np.arange(8.0, 20.0, 0.01)

        gains = [gain(lufs, 1.0, c) for c in crest]

        assert _max_step(gains) < 0.2

    @pytest.mark.parametrize("lufs", [-13.0, -18.0])
    def test_no_step_across_the_peak_headroom(self, lufs):
        peaks = np.arange(-12.0, 0.0, 0.01)

        gains = [gain(lufs, 1.0, None, p) for p in peaks]

        assert _max_step(gains) < 0.05

    def test_gain_never_negative_and_never_above_the_ceiling(self):
        for lufs in np.arange(-45.0, -5.0, 0.5):
            for crest in (None, 8.0, 16.0):
                assert 0.0 <= gain(lufs, 1.0, crest) <= ALC.MAX_GAIN_DB

    def test_peak_limit_applies_in_the_moderately_loud_band_too(self):
        """It used to be skipped there, so the limit started at -14 LUFS."""
        assert gain(-13.0, 1.0, None, -1.2) == 0.0


class TestFarFieldUnchanged:
    """Away from a threshold the values are what the buckets produced."""

    def test_already_loud_gets_nothing(self):
        assert gain(-10.0) == 0.0
        assert gain(-8.0) == 0.0

    def test_moderately_loud_gets_half_the_gap(self):
        assert gain(-13.0) == pytest.approx(0.5 * (ALC.TARGET_LUFS + 13.0))

    def test_quiet_gets_intensity_times_the_gap_up_to_the_ceiling(self):
        assert gain(-16.0, 0.5) == pytest.approx(0.5 * (ALC.TARGET_LUFS + 16.0))
        assert gain(-30.0) == pytest.approx(6.0)

    @pytest.mark.parametrize("crest,ceiling", [(None, 6.0), (10.0, 6.0), (13.5, 5.0), (17.0, 4.0)])
    def test_crest_ceilings(self, crest, ceiling):
        assert gain(-30.0, 1.0, crest) == pytest.approx(ceiling)

    def test_peak_headroom_limits_the_boost(self):
        assert gain(-30.0, 1.0, None, -4.5) == pytest.approx(3.0)


class TestBassBranchRemoved:
    def test_the_dead_parameters_are_gone(self):
        names = inspect.signature(ALC.calculate_adaptive_gain).parameters

        assert "bass_pct" not in names and "transient_density" not in names

    def test_no_reasoning_claims_a_bass_reduction(self):
        for lufs in np.arange(-40.0, -8.0, 1.0):
            assert "bass" not in ALC.calculate_adaptive_gain(lufs, 1.0, 12.0)[1].lower()


def test_stereo_width_targets_either_side_of_the_old_dead_band_differ_only_slightly():
    """The ``|target - 0.5| > 0.1`` dead-band went in #6192; pin the continuity."""
    from auralis.core.processing.base.stereo_width_processor import StereoWidthProcessor

    rng = np.random.default_rng(0)
    audio = (rng.standard_normal((44100, 2)) * 0.1).astype(np.float32)

    def side_rms(target: float) -> float:
        out = StereoWidthProcessor.apply_stereo_width_safe(audio, 0.5, target, -20.0, 44100)
        return float(np.sqrt(np.mean(((out[:, 0] - out[:, 1]) / 2) ** 2)))

    assert abs(side_rms(0.61) - side_rms(0.59)) < 0.05 * side_rms(0.60)
