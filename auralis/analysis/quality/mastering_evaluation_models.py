"""Continuous before/after measurements for mastering evaluation."""

from dataclasses import asdict, dataclass
from typing import Any

DIMENSION_FIELDS: dict[str, str] = {
    "frequency_response": "frequency_response_score",
    "dynamic_range": "dynamic_range_score",
    "stereo_imaging": "stereo_imaging_score",
    "distortion": "distortion_score",
    "loudness": "loudness_score",
}


@dataclass(frozen=True)
class DimensionEvaluation:
    """Continuous before/after measurements for one quality dimension."""

    name: str
    before_score: float
    after_score: float
    score_change: float
    mean_window_change: float
    minimum_window_change: float
    maximum_window_change: float


@dataclass(frozen=True)
class MasteringEvaluationReport:
    """Machine-readable measurements with no verdict or processing gate."""

    windows_evaluated: int
    overall_score_before: float
    overall_score_after: float
    overall_score_change: float
    sample_count_change: int
    max_true_peak_after_dbfs: float | None
    dimensions: dict[str, DimensionEvaluation]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
