"""Contract tests for the similarity /explain and /compare response models.

Covers the F6-01/02/03 cluster (#4415, #4416, #4417):
  - SimilarityExplanation accepts the engine payload without ValidationError
    (previously top_differences: list[dict[str, float]] rejected the string
    `dimension` value -> unconditional HTTP 500).
  - all_contributions survives as an array of DimensionContribution.
  - ComparisonResult echoes both track ids.
"""

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from routers.similarity import (  # noqa: E402
    ComparisonResult,
    DimensionContribution,
    SimilarityExplanation,
)


def _engine_explanation_payload() -> dict:
    """Mirror auralis/analysis/fingerprint/similarity.get_similarity_explanation."""
    def entry(dim: str, contrib: float, v1: float, v2: float) -> dict:
        return {
            "dimension": dim,
            "contribution": contrib,
            "value1": v1,
            "value2": v2,
            "difference": v1 - v2,
        }

    return {
        "track_id1": 1,
        "track_id2": 2,
        "distance": 0.42,
        "similarity_score": 0.71,
        "top_differences": [entry("lufs", 0.3, -14.0, -9.0), entry("crest_db", 0.2, 8.0, 6.0)],
        "all_contributions": [
            entry("lufs", 0.3, -14.0, -9.0),
            entry("crest_db", 0.2, 8.0, 6.0),
            entry("tempo_bpm", 0.1, 120.0, 118.0),
        ],
    }


def test_explanation_accepts_engine_payload_no_validation_error():
    """The string `dimension` value must not raise (regression for #4415)."""
    model = SimilarityExplanation(**_engine_explanation_payload())

    assert model.top_differences[0].dimension == "lufs"
    assert isinstance(model.top_differences[0], DimensionContribution)
    assert model.top_differences[0].value1 == -14.0


def test_all_contributions_is_array_of_dimension_contribution():
    """all_contributions survives serialization as an array (#4416)."""
    model = SimilarityExplanation(**_engine_explanation_payload())
    dumped = model.model_dump()

    assert isinstance(dumped["all_contributions"], list)
    assert len(dumped["all_contributions"]) == 3
    assert dumped["all_contributions"][0]["dimension"] == "lufs"
    assert dumped["all_contributions"][0]["difference"] == pytest.approx(-5.0)


def test_dimension_contribution_values_are_optional():
    """A partial payload (no value1/value2) must still validate (#4415)."""
    dc = DimensionContribution(dimension="lufs", contribution=0.3)
    assert dc.value1 is None and dc.value2 is None and dc.difference is None


def test_comparison_result_echoes_both_track_ids():
    """/compare model carries track_id1 and track_id2 (#4417)."""
    result = ComparisonResult(
        track_id1=1, track_id2=2, distance=0.42, similarity_score=0.71
    )
    dumped = result.model_dump()

    assert dumped["track_id1"] == 1
    assert dumped["track_id2"] == 2
    assert set(dumped) == {"track_id1", "track_id2", "distance", "similarity_score"}
