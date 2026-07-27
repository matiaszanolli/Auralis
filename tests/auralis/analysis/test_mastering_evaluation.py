"""Closed-loop mastering diagnosis and acceptance tests."""

from __future__ import annotations

import numpy as np
import soundfile as sf

from auralis.analysis.quality.mastering_evaluation import MasteringEvaluator
from auralis.analysis.quality.mastering_evaluation_models import EvaluationPolicy
from auralis.analysis.quality.mastering_file_evaluation import (
    evaluate_mastering_files,
)
from auralis.analysis.quality.quality_metrics import QualityMetrics, QualityScores
from auralis.analysis.quality_assessors.utilities.scoring_ops import (
    ScoringOperations,
)


def _scores(
    *,
    frequency: float = 80.0,
    dynamics: float = 80.0,
    stereo: float = 80.0,
    distortion: float = 80.0,
    loudness: float = 80.0,
    true_peak: float = -1.0,
) -> QualityScores:
    values = [frequency, dynamics, stereo, distortion, loudness]
    return QualityScores(
        overall_score=float(np.mean(values)),
        frequency_response_score=frequency,
        dynamic_range_score=dynamics,
        stereo_imaging_score=stereo,
        distortion_score=distortion,
        loudness_score=loudness,
        quality_category="",
        detailed_metrics={
            "loudness_measurement": {"true_peak": true_peak},
        },
    )


def test_detects_sustained_issue_and_accepts_meaningful_correction():
    evaluator = MasteringEvaluator(policy=EvaluationPolicy())
    before = [
        _scores(frequency=45.0),
        _scores(frequency=50.0),
        _scores(frequency=70.0),
    ]
    after = [
        _scores(frequency=69.0),
        _scores(frequency=71.0),
        _scores(frequency=72.0),
    ]

    report = evaluator.evaluate_scores(before, after)

    assert report.needs_processing is True
    assert report.should_bypass is False
    assert report.accepted is True
    assert report.verdict == "improved"
    assert report.improved_dimensions == ("frequency_response",)
    assert report.dimensions["frequency_response"].issue_window_fraction == 2 / 3


def test_localized_issue_is_not_hidden_by_track_median():
    evaluator = MasteringEvaluator()
    before = [_scores() for _ in range(5)]
    after = [_scores() for _ in range(5)]
    before[2] = _scores(frequency=45.0)
    after[2] = _scores(frequency=70.0)

    report = evaluator.evaluate_scores(before, after)

    assert report.dimensions["frequency_response"].issue_window_fraction == 0.2
    assert report.improved_dimensions == ("frequency_response",)
    assert report.accepted is True


def test_rejects_underwhelming_change_below_minimum_effect():
    evaluator = MasteringEvaluator(
        policy=EvaluationPolicy(minimum_effect=2.0)
    )

    report = evaluator.evaluate_scores(
        [_scores(frequency=45.0)],
        [_scores(frequency=46.0)],
    )

    assert report.needs_processing is True
    assert report.meaningful_improvement is False
    assert report.accepted is False
    assert report.verdict == "rejected"


def test_rejects_cross_dimensional_regression():
    evaluator = MasteringEvaluator(
        policy=EvaluationPolicy(maximum_dimension_regression=5.0)
    )

    report = evaluator.evaluate_scores(
        [_scores(frequency=40.0, dynamics=80.0)],
        [_scores(frequency=72.0, dynamics=70.0)],
    )

    assert report.meaningful_improvement is True
    assert report.regressed_dimensions == ("dynamic_range",)
    assert report.accepted is False


def test_already_good_track_recommends_bypass_when_preserved():
    evaluator = MasteringEvaluator()

    report = evaluator.evaluate_scores(
        [_scores()],
        [_scores(frequency=80.5, loudness=79.5)],
    )

    assert report.needs_processing is False
    assert report.should_bypass is True
    assert report.accepted is True
    assert report.verdict == "bypass"


def test_already_good_track_rejects_needless_material_change():
    evaluator = MasteringEvaluator(
        policy=EvaluationPolicy(bypass_score_tolerance=2.0)
    )

    report = evaluator.evaluate_scores(
        [_scores()],
        [_scores(frequency=84.0)],
    )

    assert report.should_bypass is True
    assert report.accepted is False


def test_true_peak_violation_rejects_otherwise_improved_output():
    evaluator = MasteringEvaluator(
        policy=EvaluationPolicy(true_peak_ceiling_dbfs=-0.5)
    )

    report = evaluator.evaluate_scores(
        [_scores(frequency=40.0)],
        [_scores(frequency=70.0, true_peak=0.1)],
    )

    assert "true_peak_ceiling_exceeded" in report.artifact_violations
    assert report.accepted is False


def test_negative_true_peak_threshold_penalizes_overshoot():
    assert ScoringOperations.threshold_score(-1.5, -1.0) == 100.0
    assert ScoringOperations.threshold_score(-0.5, -1.0) == 50.0
    assert ScoringOperations.threshold_score(0.0, -1.0) == 0.0


def test_evaluates_enriched_quality_comparison():
    evaluator = MasteringEvaluator()
    comparison = {
        "audio1_score": 72.0,
        "audio2_score": 80.0,
        "sub_scores": {
            "audio1": {
                "frequency_response": 40.0,
                "dynamic_range": 80.0,
                "stereo_imaging": 80.0,
                "distortion": 80.0,
                "loudness": 80.0,
            },
            "audio2": {
                "frequency_response": 70.0,
                "dynamic_range": 80.0,
                "stereo_imaging": 80.0,
                "distortion": 80.0,
                "loudness": 80.0,
            },
        },
    }

    report = evaluator.evaluate_comparison(comparison)

    assert report.accepted is True
    assert report.improved_dimensions == ("frequency_response",)


def test_quality_comparison_exposes_absolute_sub_scores(monkeypatch):
    metrics = QualityMetrics()
    score_sequence = iter([
        _scores(frequency=40.0),
        _scores(frequency=70.0),
    ])
    monkeypatch.setattr(metrics, "assess_quality", lambda _audio: next(score_sequence))

    comparison = metrics.compare_quality(
        np.zeros(8, dtype=np.float32),
        np.zeros(8, dtype=np.float32),
    )

    assert comparison["sub_scores"]["audio1"]["frequency_response"] == 40.0
    assert comparison["sub_scores"]["audio2"]["frequency_response"] == 70.0


def test_file_adapter_uses_distributed_aligned_windows(tmp_path, monkeypatch):
    sample_rate = 8000
    t = np.arange(sample_rate * 2, dtype=np.float32) / sample_rate
    source = 0.1 * np.sin(2 * np.pi * 440 * t)
    mastered = 0.2 * np.sin(2 * np.pi * 440 * t)
    source_path = tmp_path / "source.wav"
    mastered_path = tmp_path / "mastered.wav"
    sf.write(source_path, source, sample_rate, subtype="FLOAT")
    sf.write(mastered_path, mastered, sample_rate, subtype="FLOAT")

    class _FakeQualityMetrics:
        def __init__(self, *_args, **_kwargs):
            pass

        def assess_quality(self, audio):
            frequency = 70.0 if np.max(np.abs(audio)) > 0.15 else 40.0
            return _scores(frequency=frequency)

    monkeypatch.setattr(
        "auralis.analysis.quality.mastering_file_evaluation.QualityMetrics",
        _FakeQualityMetrics,
    )

    report = evaluate_mastering_files(
        source_path,
        mastered_path,
        window_seconds=0.5,
        window_count=3,
        target_lufs=-11.0,
    )

    assert report.windows_evaluated == 3
    assert report.accepted is True
    assert report.improved_dimensions == ("frequency_response",)
