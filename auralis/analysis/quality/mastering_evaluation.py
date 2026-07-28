"""Continuous mastering measurements without classification or gating."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .mastering_evaluation_models import (
    DIMENSION_FIELDS,
    DimensionEvaluation,
    MasteringEvaluationReport,
)
from .quality_metrics import QualityMetrics, QualityScores


class MasteringEvaluator:
    """Measure before/after quality scores without issuing a verdict."""

    def __init__(
        self,
        sample_rate: int = 44100,
        quality_metrics: QualityMetrics | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.quality_metrics = quality_metrics

    def evaluate_audio(
        self,
        before_audio: np.ndarray,
        after_audio: np.ndarray,
    ) -> MasteringEvaluationReport:
        """Assess one aligned input/output audio pair."""
        return self.evaluate_windows([before_audio], [after_audio])

    def evaluate_windows(
        self,
        before_windows: Sequence[np.ndarray],
        after_windows: Sequence[np.ndarray],
        *,
        sample_count_change: int | None = None,
    ) -> MasteringEvaluationReport:
        """Assess aligned program windows and aggregate them robustly by median."""
        if not before_windows or len(before_windows) != len(after_windows):
            raise ValueError("Before/after windows must be non-empty and aligned")

        before_scores: list[QualityScores] = []
        after_scores: list[QualityScores] = []
        if self.quality_metrics is None:
            self.quality_metrics = QualityMetrics(self.sample_rate)

        measured_sample_count_change = 0
        for before, after in zip(before_windows, after_windows, strict=True):
            if not isinstance(before, np.ndarray) or not isinstance(after, np.ndarray):
                raise TypeError("Audio windows must be NumPy arrays")
            if before.size == 0 or after.size == 0:
                raise ValueError("Audio windows cannot be empty")
            if not np.all(np.isfinite(before)):
                raise ValueError("Source audio contains NaN or infinite samples")
            if not np.all(np.isfinite(after)):
                raise ValueError("Output audio contains NaN or infinite samples")
            measured_sample_count_change += len(after) - len(before)

            before_scores.append(self.quality_metrics.assess_quality(before))
            after_scores.append(self.quality_metrics.assess_quality(after))

        return self.evaluate_scores(
            before_scores,
            after_scores,
            sample_count_change=(
                measured_sample_count_change
                if sample_count_change is None
                else sample_count_change
            ),
        )

    def evaluate_comparison(
        self,
        comparison: Mapping[str, Any],
    ) -> MasteringEvaluationReport:
        """Evaluate the enriched output of ``QualityMetrics.compare_quality``."""
        sub_scores = comparison.get("sub_scores")
        if not isinstance(sub_scores, Mapping):
            raise TypeError("Quality comparison does not include absolute sub-scores")

        def build_scores(key: str, overall_key: str) -> QualityScores:
            values = sub_scores.get(key)
            if not isinstance(values, Mapping):
                raise TypeError(f"Quality comparison is missing {key} sub-scores")
            missing = set(DIMENSION_FIELDS) - set(values)
            if missing:
                raise ValueError(f"Quality comparison is missing: {sorted(missing)}")
            return QualityScores(
                overall_score=float(comparison[overall_key]),
                frequency_response_score=float(values["frequency_response"]),
                dynamic_range_score=float(values["dynamic_range"]),
                stereo_imaging_score=float(values["stereo_imaging"]),
                distortion_score=float(values["distortion"]),
                loudness_score=float(values["loudness"]),
                quality_category="",
                detailed_metrics={},
            )

        return self.evaluate_scores(
            [build_scores("audio1", "audio1_score")],
            [build_scores("audio2", "audio2_score")],
        )

    def evaluate_scores(
        self,
        before_scores: Sequence[QualityScores],
        after_scores: Sequence[QualityScores],
        *,
        sample_count_change: int = 0,
    ) -> MasteringEvaluationReport:
        """Measure precomputed window scores without threshold decisions."""
        if not before_scores or len(before_scores) != len(after_scores):
            raise ValueError("Before/after score windows must be non-empty and aligned")

        dimensions: dict[str, DimensionEvaluation] = {}

        for name, field_name in DIMENSION_FIELDS.items():
            before_values = np.asarray(
                [float(getattr(score, field_name)) for score in before_scores]
            )
            after_values = np.asarray(
                [float(getattr(score, field_name)) for score in after_scores]
            )
            before = float(np.median(before_values))
            after = float(np.median(after_values))
            window_changes = after_values - before_values

            dimensions[name] = DimensionEvaluation(
                name=name,
                before_score=before,
                after_score=after,
                score_change=after - before,
                mean_window_change=float(np.mean(window_changes)),
                minimum_window_change=float(np.min(window_changes)),
                maximum_window_change=float(np.max(window_changes)),
            )

        overall_before = float(np.median([
            score.overall_score for score in before_scores
        ]))
        overall_after = float(np.median([
            score.overall_score for score in after_scores
        ]))

        return MasteringEvaluationReport(
            windows_evaluated=len(before_scores),
            overall_score_before=overall_before,
            overall_score_after=overall_after,
            overall_score_change=overall_after - overall_before,
            sample_count_change=sample_count_change,
            max_true_peak_after_dbfs=self._max_true_peak(after_scores),
            dimensions=dimensions,
        )

    @staticmethod
    def _max_true_peak(scores: Sequence[QualityScores]) -> float | None:
        peaks = [
            float(value)
            for score in scores
            if (
                value := score.detailed_metrics.get(
                    "loudness_measurement", {}
                ).get("true_peak")
            ) is not None
        ]
        return max(peaks, default=None)
