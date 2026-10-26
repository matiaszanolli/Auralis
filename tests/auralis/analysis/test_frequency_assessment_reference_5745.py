"""FrequencyResponseAssessor scores spectral shape against a tilted reference (#5745).

The reference used to be a flat 0 dB compared with absolute FFT magnitudes:
empty low bands (no FFT bin) contributed ~13 dB of the mean deviation, white
noise outscored pink, level mattered, and no input could exceed ~74.
"""

import numpy as np
import pytest

from auralis.analysis.quality.frequency_assessment import FrequencyResponseAssessor
from auralis.analysis.quality.quality_metrics import QualityMetrics
from auralis.analysis.spectrum_bands import populated_band_mask

SR = 44100


def _pink(seconds: float, seed: int = 0) -> np.ndarray:
    n = int(seconds * SR)
    spectrum = np.fft.rfft(np.random.default_rng(seed).standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1 / SR)
    spectrum[1:] /= np.sqrt(freqs[1:])
    audio = np.fft.irfft(spectrum, n)
    return audio / np.max(np.abs(audio)) * 0.5


def _white(seconds: float, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(int(seconds * SR)) * 0.15


@pytest.fixture(scope="module")
def metrics() -> QualityMetrics:
    return QualityMetrics(SR)


def _score(metrics: QualityMetrics, audio: np.ndarray) -> float:
    metrics.spectrum_analyzer.reset_smoothing()
    result = metrics.spectrum_analyzer.analyze_file(audio)
    return metrics.frequency_assessor.assess(result)


def test_pink_noise_scores_at_least_as_well_as_white_noise(metrics):
    assert _score(metrics, _pink(8.0)) >= _score(metrics, _white(8.0))


def test_pink_noise_scores_high(metrics):
    assert _score(metrics, _pink(8.0)) > 85.0


def test_the_score_does_not_depend_on_level(metrics):
    pink = _pink(8.0)

    assert _score(metrics, pink * 0.1) == pytest.approx(_score(metrics, pink), abs=1.0)


def test_a_spectrum_equal_to_the_reference_scores_near_100(metrics):
    assessor = metrics.frequency_assessor

    for offset in (0.0, -40.0, 25.0):
        result = {'spectrum': (assessor.reference_curve + offset).tolist(),
                  'frequency_bins': assessor.frequency_bins.tolist()}
        assert assessor.assess(result) >= 95.0


def test_bands_without_an_fft_bin_do_not_count(metrics):
    assessor = metrics.frequency_assessor
    empty = ~assessor.populated_bands
    assert empty.any(), "the 128-band / 8192-point setup has bands between FFT bins"

    clean = assessor.reference_curve.copy()
    garbage = clean.copy()
    garbage[empty] = -130.0
    bins = assessor.frequency_bins.tolist()

    assert assessor.assess({'spectrum': garbage.tolist(), 'frequency_bins': bins}) == pytest.approx(
        assessor.assess({'spectrum': clean.tolist(), 'frequency_bins': bins})
    )


def test_unresolved_bands_are_not_reported_as_problem_frequencies(metrics):
    assessor = metrics.frequency_assessor
    spectrum = assessor.reference_curve.copy()
    spectrum[~assessor.populated_bands] = -130.0

    issues = assessor.identify_frequency_issues(
        {'spectrum': spectrum.tolist(), 'frequency_bins': assessor.frequency_bins.tolist()}
    )

    assert issues['problem_frequencies'] == []
    assert not issues['lacking_bass']


def test_without_fft_geometry_every_band_counts():
    bins = np.geomspace(20, 20000, 32)

    assert FrequencyResponseAssessor(bins).populated_bands.all()


def test_populated_band_mask_marks_bands_between_bins():
    frequencies = np.fft.rfftfreq(8192, 1 / SR)
    bins = np.geomspace(20, 20000, 128)

    mask = populated_band_mask(frequencies, bins)

    assert not mask[0] and mask[-1]


def test_digital_silence_has_no_frequency_response_to_score(metrics):
    assert _score(metrics, np.zeros(4 * SR)) == 0.0
