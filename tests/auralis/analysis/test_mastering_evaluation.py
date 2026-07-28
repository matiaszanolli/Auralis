"""Continuous mastering measurements without categorical decisions."""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from auralis.analysis.quality.mastering_evaluation import MasteringEvaluator
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


def test_reports_numeric_changes_without_a_verdict():
    report = MasteringEvaluator().evaluate_scores(
        [_scores(frequency=45.0)],
        [_scores(frequency=69.0)],
    )

    assert report.overall_score_change == pytest.approx(4.8)
    assert report.dimensions["frequency_response"].score_change == 24.0
    serialized = report.to_dict()
    assert "verdict" not in serialized
    assert "accepted" not in serialized
    assert "should_bypass" not in serialized


def test_aggregates_all_windows_without_threshold_selection():
    report = MasteringEvaluator().evaluate_scores(
        [
            _scores(frequency=45.0),
            _scores(frequency=80.0),
            _scores(frequency=70.0),
        ],
        [
            _scores(frequency=69.0),
            _scores(frequency=78.0),
            _scores(frequency=72.0),
        ],
    )

    frequency = report.dimensions["frequency_response"]
    assert frequency.before_score == 70.0
    assert frequency.after_score == 72.0
    assert frequency.score_change == 2.0
    assert frequency.mean_window_change == 8.0
    assert frequency.minimum_window_change == -2.0
    assert frequency.maximum_window_change == 24.0


def test_reports_sample_count_change_as_a_number():
    class _Metrics:
        @staticmethod
        def assess_quality(_audio):
            return _scores()

    report = MasteringEvaluator(quality_metrics=_Metrics()).evaluate_windows(
        [np.zeros(8, dtype=np.float32)],
        [np.zeros(6, dtype=np.float32)],
    )

    assert report.sample_count_change == -2


def test_true_peak_is_reported_without_acceptance_decision():
    report = MasteringEvaluator().evaluate_scores(
        [_scores(frequency=40.0)],
        [_scores(frequency=70.0, true_peak=0.1)],
    )

    assert report.max_true_peak_after_dbfs == 0.1
    assert "artifact_violations" not in report.to_dict()


def test_negative_true_peak_threshold_penalizes_overshoot():
    assert ScoringOperations.threshold_score(-1.5, -1.0) == 100.0
    assert ScoringOperations.threshold_score(-0.5, -1.0) == 50.0
    assert ScoringOperations.threshold_score(0.0, -1.0) == 0.0


def test_evaluates_enriched_quality_comparison_as_measurements():
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

    report = MasteringEvaluator().evaluate_comparison(comparison)

    assert report.overall_score_change == 8.0
    assert report.dimensions["frequency_response"].score_change == 30.0


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
    assert report.sample_count_change == 0
    assert report.dimensions["frequency_response"].score_change == 30.0
