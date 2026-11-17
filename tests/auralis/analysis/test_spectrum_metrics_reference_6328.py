"""spectral_centroid and the peak levels are computed on the right scale (#6328).

The analyzer's per-band spectrum is in dB relative to its loudest band, and the centroid weighted by those
non-positive values: a 200 Hz and an 8 kHz tone read nearly the same centroid. The peak-level fields used the same
relative reference, so a -2.5 dBFS and a -22.5 dBFS sine reported identical `max_peak_level_db` (0.0).
"""

import numpy as np
import pytest

from auralis.analysis.dynamic_range import DynamicRangeAnalyzer
from auralis.analysis.spectrum_operations import SpectrumOperations

SR = 44100


def test_centroid_follows_the_dominant_band_in_a_relative_db_spectrum():
    bins = np.array([100.0, 1000.0, 10000.0])

    low = SpectrumOperations.calculate_spectral_centroid(bins, np.array([0.0, -40.0, -80.0]))
    high = SpectrumOperations.calculate_spectral_centroid(bins, np.array([-80.0, -40.0, 0.0]))

    assert low < 300.0
    assert high > 5000.0


def test_centroid_of_a_linear_spectrum_is_unchanged():
    bins = np.array([100.0, 200.0])

    assert SpectrumOperations.calculate_spectral_centroid(bins, np.array([1.0, 1.0])) == pytest.approx(150.0)


def _peak_stats(amplitude: float) -> dict:
    analyzer = DynamicRangeAnalyzer(SR)
    t = np.arange(SR * 2) / SR
    audio = (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    return analyzer._analyze_peak_distribution(audio)


def test_peak_levels_are_absolute_dbfs():
    loud, quiet = _peak_stats(10 ** (-2.5 / 20)), _peak_stats(10 ** (-22.5 / 20))

    assert loud["max_peak_level_db"] == pytest.approx(-2.5, abs=0.2)
    assert quiet["max_peak_level_db"] == pytest.approx(-22.5, abs=0.2)
