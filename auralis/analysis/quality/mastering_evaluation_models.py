"""Data models and policy for closed-loop mastering evaluation."""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

DIMENSION_FIELDS: dict[str, str] = {
    "frequency_response": "frequency_response_score",
    "dynamic_range": "dynamic_range_score",
    "stereo_imaging": "stereo_imaging_score",
    "distortion": "distortion_score",
    "loudness": "loudness_score",
}


@dataclass(frozen=True)
class EvaluationPolicy:
    """Thresholds for deciding whether mastering was useful and safe."""

    issue_score_threshold: float = 60.0
    target_score: float = 75.0
    minimum_effect: float = 2.0
    minimum_total_distance_reduction: float = 2.0
    maximum_dimension_regression: float = 5.0
    bypass_score_tolerance: float = 2.0
    minimum_issue_window_fraction: float = 0.2
    true_peak_ceiling_dbfs: float = 0.0

    def __post_init__(self) -> None:
        score_values = (
            self.issue_score_threshold,
            self.target_score,
            self.minimum_effect,
            self.minimum_total_distance_reduction,
            self.maximum_dimension_regression,
            self.bypass_score_tolerance,
        )
        if not all(np.isfinite(value) for value in score_values):
            raise ValueError("Evaluation thresholds must be finite")
        if not 0.0 <= self.issue_score_threshold <= 100.0:
            raise ValueError("issue_score_threshold must be between 0 and 100")
        if not 0.0 <= self.target_score <= 100.0:
            raise ValueError("target_score must be between 0 and 100")
        if any(value < 0.0 for value in score_values[2:]):
            raise ValueError("Effect and regression thresholds cannot be negative")
        if not 0.0 <= self.minimum_issue_window_fraction <= 1.0:
            raise ValueError("minimum_issue_window_fraction must be between 0 and 1")


@dataclass(frozen=True)
class DimensionEvaluation:
    """Before/after outcome for one independently scored quality dimension."""

    name: str
    before_score: float
    after_score: float
    target_score: float
    issue_window_fraction: float
    issue_detected: bool
    regression_window_fraction: float
    material_change_window_fraction: float
    materially_changed: bool
    score_change: float
    distance_before: float
    distance_after: float
    distance_reduction: float
    meaningfully_improved: bool
    regressed: bool


@dataclass(frozen=True)
class MasteringEvaluationReport:
    """Machine-readable closed-loop verdict for one mastering operation."""

    needs_processing: bool
    should_bypass: bool
    accepted: bool
    meaningful_improvement: bool
    windows_evaluated: int
    overall_score_before: float
    overall_score_after: float
    overall_score_change: float
    total_distance_before: float
    total_distance_after: float
    total_distance_reduction: float
    improved_dimensions: tuple[str, ...]
    regressed_dimensions: tuple[str, ...]
    artifact_violations: tuple[str, ...]
    dimensions: dict[str, DimensionEvaluation]

    @property
    def verdict(self) -> str:
        if self.accepted and self.should_bypass:
            return "bypass"
        if self.accepted:
            return "improved"
        return "rejected"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["verdict"] = self.verdict
        return result
