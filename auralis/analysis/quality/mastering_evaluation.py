"""
Closed-loop mastering evaluation.

Turns the existing quality sub-scores into two explicit decisions:

1. Does the source contain at least one sustained quality issue?
2. Did the mastered output improve a diagnosed dimension without regressing
   another dimension or violating signal-integrity constraints?
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .mastering_evaluation_models import (
    DIMENSION_FIELDS,
    DimensionEvaluation,
    EvaluationPolicy,
    MasteringEvaluationReport,
)
from .quality_metrics import QualityMetrics, QualityScores


class MasteringEvaluator:
    """Evaluate quality scores or audio using a shared decision policy."""

    def __init__(
        self,
        sample_rate: int = 44100,
        policy: EvaluationPolicy | None = None,
        quality_metrics: QualityMetrics | None = None,
    ) -> None:
        self.policy = policy or EvaluationPolicy()
        self.sample_rate = sample_rate
        self.quality_metrics = quality_metrics

    def evaluate_audio(
        self,
        before_audio: np.ndarray,
        after_audio: np.ndarray,
        target_scores: Mapping[str, float] | None = None,
    ) -> MasteringEvaluationReport:
        """Assess one aligned input/output audio pair."""
        return self.evaluate_windows(
            [before_audio],
            [after_audio],
            target_scores=target_scores,
        )

    def evaluate_windows(
        self,
        before_windows: Sequence[np.ndarray],
        after_windows: Sequence[np.ndarray],
        target_scores: Mapping[str, float] | None = None,
        artifact_violations: Sequence[str] = (),
    ) -> MasteringEvaluationReport:
        """Assess aligned program windows and aggregate them robustly by median."""
        if not before_windows or len(before_windows) != len(after_windows):
            raise ValueError("Before/after windows must be non-empty and aligned")

        violations = list(artifact_violations)
        before_scores: list[QualityScores] = []
        after_scores: list[QualityScores] = []
        if self.quality_metrics is None:
            self.quality_metrics = QualityMetrics(self.sample_rate)

        for before, after in zip(before_windows, after_windows, strict=True):
            if not isinstance(before, np.ndarray) or not isinstance(after, np.ndarray):
                raise TypeError("Audio windows must be NumPy arrays")
            if before.size == 0 or after.size == 0:
                raise ValueError("Audio windows cannot be empty")
            if not np.all(np.isfinite(before)):
                raise ValueError("Source audio contains NaN or infinite samples")
            if not np.all(np.isfinite(after)):
                violations.append("output_non_finite")
                after = np.nan_to_num(after, copy=True)
            if len(before) != len(after):
                violations.append("sample_count_changed")

            before_scores.append(self.quality_metrics.assess_quality(before))
            after_scores.append(self.quality_metrics.assess_quality(after))

        return self.evaluate_scores(
            before_scores,
            after_scores,
            target_scores=target_scores,
            artifact_violations=violations,
        )

    def evaluate_comparison(
        self,
        comparison: Mapping[str, Any],
        target_scores: Mapping[str, float] | None = None,
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
            target_scores=target_scores,
        )

    def evaluate_scores(
        self,
        before_scores: Sequence[QualityScores],
        after_scores: Sequence[QualityScores],
        target_scores: Mapping[str, float] | None = None,
        artifact_violations: Sequence[str] = (),
    ) -> MasteringEvaluationReport:
        """Evaluate precomputed window scores without rerunning audio analysis."""
        if not before_scores or len(before_scores) != len(after_scores):
            raise ValueError("Before/after score windows must be non-empty and aligned")

        targets = self._normalize_targets(target_scores)
        dimensions: dict[str, DimensionEvaluation] = {}

        for name, field_name in DIMENSION_FIELDS.items():
            before_values = np.asarray(
                [float(getattr(score, field_name)) for score in before_scores]
            )
            after_values = np.asarray(
                [float(getattr(score, field_name)) for score in after_scores]
            )
            target = targets[name]
            issue_mask = before_values < self.policy.issue_score_threshold
            issue_fraction = float(np.mean(issue_mask))
            issue_detected = (
                issue_fraction >= self.policy.minimum_issue_window_fraction
            )
            evaluation_mask = (
                issue_mask if issue_detected else np.ones_like(issue_mask)
            )
            before = float(np.median(before_values[evaluation_mask]))
            after = float(np.median(after_values[evaluation_mask]))
            window_changes = after_values - before_values
            regression_fraction = float(np.mean(
                window_changes < -self.policy.maximum_dimension_regression
            ))
            material_change_fraction = float(np.mean(
                np.abs(window_changes) > self.policy.bypass_score_tolerance
            ))
            distance_before = max(0.0, target - before)
            distance_after = max(0.0, target - after)
            distance_reduction = distance_before - distance_after
            score_change = after - before

            dimensions[name] = DimensionEvaluation(
                name=name,
                before_score=before,
                after_score=after,
                target_score=target,
                issue_window_fraction=issue_fraction,
                issue_detected=issue_detected,
                regression_window_fraction=regression_fraction,
                material_change_window_fraction=material_change_fraction,
                materially_changed=(
                    material_change_fraction
                    >= self.policy.minimum_issue_window_fraction
                ),
                score_change=score_change,
                distance_before=distance_before,
                distance_after=distance_after,
                distance_reduction=distance_reduction,
                meaningfully_improved=(
                    issue_detected
                    and distance_reduction >= self.policy.minimum_effect
                ),
                regressed=(
                    regression_fraction
                    >= self.policy.minimum_issue_window_fraction
                ),
            )

        violations = list(dict.fromkeys(artifact_violations))
        max_true_peak = self._max_true_peak(after_scores)
        if max_true_peak > self.policy.true_peak_ceiling_dbfs:
            violations.append("true_peak_ceiling_exceeded")

        improved = tuple(
            name for name, result in dimensions.items()
            if result.meaningfully_improved
        )
        regressed = tuple(
            name for name, result in dimensions.items() if result.regressed
        )
        needs_processing = any(
            result.issue_detected for result in dimensions.values()
        )
        before_total = float(sum(
            result.distance_before for result in dimensions.values()
        ))
        after_total = float(sum(
            result.distance_after for result in dimensions.values()
        ))
        total_reduction = before_total - after_total
        overall_before = float(np.median([
            score.overall_score for score in before_scores
        ]))
        overall_after = float(np.median([
            score.overall_score for score in after_scores
        ]))

        meaningful_improvement = bool(improved)
        if needs_processing:
            accepted = (
                meaningful_improvement
                and total_reduction >= self.policy.minimum_total_distance_reduction
                and not regressed
                and not violations
            )
        else:
            accepted = (
                not any(result.materially_changed for result in dimensions.values())
                and not violations
            )

        return MasteringEvaluationReport(
            needs_processing=needs_processing,
            should_bypass=not needs_processing,
            accepted=accepted,
            meaningful_improvement=meaningful_improvement,
            windows_evaluated=len(before_scores),
            overall_score_before=overall_before,
            overall_score_after=overall_after,
            overall_score_change=overall_after - overall_before,
            total_distance_before=before_total,
            total_distance_after=after_total,
            total_distance_reduction=total_reduction,
            improved_dimensions=improved,
            regressed_dimensions=regressed,
            artifact_violations=tuple(dict.fromkeys(violations)),
            dimensions=dimensions,
        )

    def _normalize_targets(
        self, target_scores: Mapping[str, float] | None
    ) -> dict[str, float]:
        targets = dict.fromkeys(DIMENSION_FIELDS, self.policy.target_score)
        if target_scores is None:
            return targets
        unknown = set(target_scores) - set(DIMENSION_FIELDS)
        if unknown:
            raise ValueError(f"Unknown quality dimensions: {sorted(unknown)}")
        for name, value in target_scores.items():
            numeric = float(value)
            if not np.isfinite(numeric) or not 0.0 <= numeric <= 100.0:
                raise ValueError(f"Target for {name} must be between 0 and 100")
            targets[name] = numeric
        return targets

    @staticmethod
    def _max_true_peak(scores: Sequence[QualityScores]) -> float:
        peaks = [
            float(score.detailed_metrics.get("loudness_measurement", {}).get(
                "true_peak", float("-inf")
            ))
            for score in scores
        ]
        return max(peaks, default=float("-inf"))
