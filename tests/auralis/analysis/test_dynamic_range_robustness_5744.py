"""DynamicRangeAnalyzer: short input, stereo layout and silence (#5744)."""

import numpy as np
import pytest

from auralis.analysis.dynamic_range import DynamicRangeAnalyzer
from auralis.analysis.quality.quality_metrics import QualityMetrics
from auralis.analysis.quality_assessors.utilities.scoring_ops import ScoringOperations

SR = 44100


def _music_like(seconds: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    envelope = 0.2 + 0.6 * (np.sin(2 * np.pi * 0.5 * t) > 0)
    return (rng.standard_normal(n) * 0.1 * envelope).astype(np.float64)


@pytest.mark.parametrize("length", [0, 1, 100, 300, 999])
def test_short_input_returns_instead_of_raising(length):
    result = DynamicRangeAnalyzer(SR).analyze_dynamic_range(np.full(length, 0.1))

    assert result['dr_value'] == 0.0
    assert np.isfinite(result['crest_factor_db'])


@pytest.mark.parametrize("length", [0, 100])
def test_short_stereo_input_returns_instead_of_raising(length):
    result = DynamicRangeAnalyzer(SR).analyze_dynamic_range(np.full((length, 2), 0.1))

    assert result['dr_value'] == 0.0


def test_dual_mono_measures_like_its_mono_twin():
    mono = _music_like(20.0)
    analyzer = DynamicRangeAnalyzer(SR)

    mono_result = analyzer.analyze_dynamic_range(mono)
    stereo_result = analyzer.analyze_dynamic_range(np.stack([mono, mono], axis=1))

    assert stereo_result['dr_value'] == pytest.approx(mono_result['dr_value'], rel=0.01)
    assert stereo_result['peak_distribution']['peak_density'] == pytest.approx(
        mono_result['peak_distribution']['peak_density'], rel=0.01
    )


def test_silence_has_a_finite_crest_factor_instead_of_nan():
    result = DynamicRangeAnalyzer(SR).analyze_dynamic_range(np.zeros((3 * SR, 2)))

    assert result['crest_factor_db'] == 0.0


def test_band_score_scores_nan_as_zero_not_as_the_top_band():
    bands = [(0, 0), (10, 50), (20, 100)]

    assert ScoringOperations.band_score(float('nan'), bands) == 0.0
    assert ScoringOperations.band_score(25.0, bands) == 100.0


def test_digital_silence_is_not_rated_fair():
    scores = QualityMetrics(SR).assess_quality(np.zeros((3 * SR, 2)))

    # 40.7 ('Fair') while the NaN crest factor took the top band.
    assert scores.overall_score < 40.0
    assert scores.dynamic_range_score == 0.0
