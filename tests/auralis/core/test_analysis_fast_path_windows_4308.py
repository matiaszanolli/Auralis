"""
Analysis fast-path FFT windows scale with sample rate (#4308).

Four analysis fast paths hardcoded small FFT window/hop sizes as bare sample
counts (512/1024/2048), silently changing the frequency/time resolution
tradeoff across sample rates (same family of bug as the already-fixed #4029/
#4030). Windows are now anchored in time via frames_for_seconds()
(auralis/dsp/utils/spectral.py), reproducing the historical 44.1kHz literals
exactly while scaling proportionally at other rates.
"""

import numpy as np

from auralis.analysis.content_aware_analyzer import ContentAwareAnalyzer
from auralis.analysis.ml.feature_extractor import FeatureExtractor
from auralis.core.analysis.content_analysis_facade import ContentAnalysisFacade
from auralis.dsp.utils.spectral import _tempo_estimate_python, frames_for_seconds


def _tone(sample_rate, duration=2.0, freq=440.0):
    n = int(sample_rate * duration)
    t = np.arange(n) / sample_rate
    return (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_frames_for_seconds_reproduces_historical_literals_at_44100():
    """The 44.1kHz path must be unchanged for every literal these sites used."""
    for n in (512, 1024, 2048):
        assert frames_for_seconds(44100, n / 44100) == n


def test_frames_for_seconds_scales_with_sample_rate():
    """Doubling the sample rate should not leave the window fixed in samples."""
    base = frames_for_seconds(44100, 512 / 44100)
    doubled = frames_for_seconds(88200, 512 / 44100)
    assert doubled > base


def test_content_analysis_facade_quick_analysis_runs_at_multiple_rates():
    for sr in (44100, 48000, 96000):
        facade = ContentAnalysisFacade(sample_rate=sr)
        result = facade.analyze_quick(_tone(sr))
        assert np.isfinite(result["spectral_centroid"])


def test_content_aware_analyzer_spectral_flux_runs_at_multiple_rates():
    analyzer = ContentAwareAnalyzer()
    for sr in (44100, 48000, 96000):
        flux = analyzer._calculate_spectral_flux(_tone(sr), sr)
        assert np.isfinite(flux)
        assert flux >= 0


def test_feature_extractor_onset_rate_runs_at_multiple_rates():
    for sr in (44100, 48000, 96000):
        extractor = FeatureExtractor(sample_rate=sr)
        onset_rate = extractor._onset_rate(_tone(sr))
        assert np.isfinite(onset_rate)
        assert onset_rate >= 0


def test_tempo_estimate_python_runs_at_multiple_rates():
    for sr in (44100, 48000, 96000):
        tempo = _tempo_estimate_python(_tone(sr, freq=2.0), sr)
        assert 60 <= tempo <= 200
