"""
Regression: distortion/noise estimators measure the signal, not the level (#5714)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`estimate_noise_floor` used to be the mean of the lowest 10 % of |x| — the
programme's own amplitude distribution — so it tracked gain 1:1 and a louder
master always scored worse. `estimate_thd` took the largest FFT bin of any
signal as "the fundamental", so white noise reported a THD of 0.36.
"""

import numpy as np
import pytest

from auralis.analysis.quality.distortion_assessment import DistortionAssessor
from auralis.analysis.quality_assessors.utilities.estimation_ops import (
    EstimationOperations as Est,
)

SR = 44100
N = SR * 5


def _pink(rng: np.random.Generator, n: int = N) -> np.ndarray:
    f = np.fft.rfftfreq(n)
    f[0] = 1.0
    spec = (rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))) / np.sqrt(f)
    x = np.fft.irfft(spec, n)
    return x / np.sqrt(np.mean(x ** 2))


def _chord_with_noise(noise_dbfs: float, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(N) / SR
    chord = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 277.18, 329.63))
    chord = 0.5 * chord / np.max(np.abs(chord))
    return chord + rng.standard_normal(N) * 10 ** (noise_dbfs / 20)


class TestNoiseIsLevelIndependent:
    @pytest.mark.parametrize("gain_db", [-40.0, -20.0, -6.0])
    def test_snr_invariant_to_gain(self, gain_db):
        pink = _pink(np.random.default_rng(1))
        ref = Est.estimate_snr_db(pink * 10 ** (-30.0 / 20))
        snr = Est.estimate_snr_db(pink * 10 ** (gain_db / 20))
        assert snr == pytest.approx(ref, abs=0.5)

    def test_chord_with_known_noise_floor(self):
        x = _chord_with_noise(-54.0, np.random.default_rng(2))
        assert Est.estimate_noise_floor(x) == pytest.approx(-54.0, abs=2.0)

    def test_scaling_moves_floor_with_signal_but_not_snr(self):
        x = _chord_with_noise(-54.0, np.random.default_rng(3))
        assert Est.estimate_noise_floor(x * 0.5) == pytest.approx(
            Est.estimate_noise_floor(x) - 6.02, abs=0.1
        )
        assert Est.estimate_snr_db(x * 0.5) == pytest.approx(Est.estimate_snr_db(x), abs=0.1)

    def test_silence_and_empty_are_safe(self):
        assert Est.estimate_snr_db(np.zeros(N)) == Est._SILENT_SNR_DB
        assert Est.estimate_noise_floor(np.zeros(0)) == -90.0

    def test_short_input_below_one_frame(self):
        assert np.isfinite(Est.estimate_noise_floor(np.random.default_rng(4).standard_normal(100)))


class TestThdOnlyWhenToneDominates:
    def test_white_noise_is_not_applicable(self):
        assert Est.estimate_thd(np.random.default_rng(5).standard_normal(N)) is None

    def test_pink_noise_is_not_applicable(self):
        assert Est.estimate_thd(_pink(np.random.default_rng(6))) is None

    def test_known_third_harmonic_is_measured(self):
        t = np.arange(N) / SR
        x = np.sin(2 * np.pi * 440 * t) + 0.05 * np.sin(2 * np.pi * 1320 * t)
        assert Est.estimate_thd(x) == pytest.approx(0.05, rel=0.05)

    def test_clean_sine_has_negligible_thd(self):
        t = np.arange(N) / SR
        thd = Est.estimate_thd(np.sin(2 * np.pi * 440 * t))
        assert thd is not None and thd < 1e-3


class TestDistortionAssessor:
    def test_score_same_for_same_signal_at_different_gain(self):
        x = np.stack([_chord_with_noise(-54.0, np.random.default_rng(7))] * 2, axis=1)
        a = DistortionAssessor().assess(x * 0.4)
        b = DistortionAssessor().assess(x * 0.8)
        assert a == pytest.approx(b, abs=1.0)

    def test_white_noise_not_flagged_as_thd_distortion(self):
        x = np.random.default_rng(8).standard_normal((N, 2)) * 0.1
        detail = DistortionAssessor().detailed_analysis(x)
        assert detail['thd'] is None
        assert detail['excessive_distortion'] is False

    def test_not_applicable_thd_does_not_inflate_or_deflate_score(self):
        """Without a THD term the remaining terms are re-weighted, not zeroed."""
        x = np.random.default_rng(9).standard_normal((N, 2)) * 0.05
        score = DistortionAssessor().assess(x)
        # Clipping term is perfect (peaks < 0.99); only the noise term can lower it.
        assert score == pytest.approx(
            DistortionAssessor().assess(x * 2.0), abs=1.0
        )
        assert 0.0 <= score <= 100.0
