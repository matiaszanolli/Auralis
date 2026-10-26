"""phase_correlation is signed: a polarity-inverted pair is -1, not a perfect 1 (#5743)."""

import numpy as np
import pytest

from auralis.analysis.phase_correlation import PhaseCorrelationAnalyzer
from auralis.analysis.quality.stereo_assessment import StereoImagingAssessor

SR = 44100


@pytest.fixture
def noise() -> np.ndarray:
    return np.random.default_rng(0).standard_normal(5 * SR) * 0.3


def _analyze(left: np.ndarray, right: np.ndarray) -> dict:
    return PhaseCorrelationAnalyzer(SR).analyze_correlation(np.stack([left, right], axis=1))


def test_in_phase_stereo_is_still_one(noise):
    assert _analyze(noise, noise)['phase_correlation'] > 0.99


def test_polarity_inverted_stereo_is_negative(noise):
    result = _analyze(noise, -noise)

    assert result['phase_correlation'] < -0.99
    assert result['correlation'] == pytest.approx(-1.0)


def test_uncorrelated_stereo_is_near_zero():
    rng = np.random.default_rng(1)

    assert abs(_analyze(rng.standard_normal(5 * SR), rng.standard_normal(5 * SR))['phase_correlation']) < 0.1


def test_polarity_inversion_does_not_score_better_than_in_phase(noise):
    assessor = StereoImagingAssessor()
    in_phase = assessor.assess(_analyze(noise, noise))
    inverted = assessor.assess(_analyze(noise, -noise))

    assert inverted < in_phase


def test_an_anti_phase_pair_scores_at_the_floor(noise):
    # Correlation, width and mono compatibility are all at their floor for
    # L = -R, so only the phase term could have rewarded it.
    assert StereoImagingAssessor().assess(_analyze(noise, -noise)) < 1.0
