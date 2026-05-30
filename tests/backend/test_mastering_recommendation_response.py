"""
Regression tests for the mastering recommendation REST/WS contract (#3840).

The fix for #3550 added ``is_hybrid`` only to the WebSocket broadcast path.
The REST endpoint ``GET /api/player/mastering/recommendation/{track_id}``
returned ``MasteringRecommendation.to_dict()`` raw, so it omitted
``is_hybrid`` / ``track_id`` (both required by the frontend types) and leaked
``created`` / ``alternative_profiles`` (not part of the REST contract).

The fix introduces ``MasteringRecommendation.to_response(track_id)`` as the
single source of truth used by BOTH paths, and a Pydantic
``MasteringRecommendationResponse`` that the REST endpoint declares as its
``response_model`` (which strips the internal-only fields).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.analysis.adaptive_mastering_engine import (
    MasteringRecommendation,
    ProfileWeight,
)
from auralis.analysis.mastering_profile import (
    PROFILE_WARM_MASTERS,
    PROFILE_BRIGHT_MASTERS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _single_rec() -> MasteringRecommendation:
    return MasteringRecommendation(
        primary_profile=PROFILE_WARM_MASTERS,
        confidence_score=0.82,
        predicted_loudness_change=-1.5,
        predicted_crest_change=0.4,
        predicted_centroid_change=120.0,
        reasoning="Single confident match",
    )


def _hybrid_rec() -> MasteringRecommendation:
    return MasteringRecommendation(
        primary_profile=PROFILE_WARM_MASTERS,
        confidence_score=0.55,
        predicted_loudness_change=-0.8,
        predicted_crest_change=0.2,
        predicted_centroid_change=60.0,
        reasoning="Blended match",
        weighted_profiles=[
            ProfileWeight(profile=PROFILE_WARM_MASTERS, weight=0.6),
            ProfileWeight(profile=PROFILE_BRIGHT_MASTERS, weight=0.4),
        ],
    )


# ---------------------------------------------------------------------------
# to_response — the shared serializer
# ---------------------------------------------------------------------------

class TestToResponse:
    def test_adds_track_id(self):
        payload = _single_rec().to_response(track_id=42)
        assert payload["track_id"] == 42

    def test_non_hybrid_sets_is_hybrid_false(self):
        payload = _single_rec().to_response(track_id=1)
        assert payload["is_hybrid"] is False

    def test_hybrid_sets_is_hybrid_true(self):
        payload = _hybrid_rec().to_response(track_id=1)
        assert payload["is_hybrid"] is True

    def test_weighted_profiles_always_present_when_non_hybrid(self):
        """The required-on-the-frontend field must never be absent."""
        payload = _single_rec().to_response(track_id=1)
        assert payload["weighted_profiles"] == []

    def test_weighted_profiles_populated_when_hybrid(self):
        payload = _hybrid_rec().to_response(track_id=1)
        ids = [wp["profile_id"] for wp in payload["weighted_profiles"]]
        assert ids == [
            PROFILE_WARM_MASTERS.profile_id,
            PROFILE_BRIGHT_MASTERS.profile_id,
        ]

    def test_carries_core_prediction_fields(self):
        payload = _single_rec().to_response(track_id=1)
        for key in (
            "primary_profile_id",
            "primary_profile_name",
            "confidence_score",
            "predicted_loudness_change",
            "predicted_crest_change",
            "predicted_centroid_change",
            "reasoning",
        ):
            assert key in payload

    def test_does_not_mutate_to_dict_contract(self):
        """to_dict (used elsewhere) must remain free of track_id/is_hybrid."""
        rec = _single_rec()
        d = rec.to_dict()
        assert "track_id" not in d
        assert "is_hybrid" not in d


# ---------------------------------------------------------------------------
# Pydantic response model — the REST contract
# ---------------------------------------------------------------------------

class TestMasteringRecommendationResponseModel:
    def test_model_accepts_to_response_payload(self):
        from schemas import MasteringRecommendationResponse

        payload = _hybrid_rec().to_response(track_id=7)
        model = MasteringRecommendationResponse(**payload)
        assert model.track_id == 7
        assert model.is_hybrid is True
        assert len(model.weighted_profiles) == 2

    def test_model_strips_leaked_internal_fields(self):
        """`created` / `alternative_profiles` are not part of the REST contract.

        to_response carries them through (from to_dict), but the response_model
        must not expose them — FastAPI filters to declared fields.
        """
        from schemas import MasteringRecommendationResponse

        payload = _single_rec().to_response(track_id=3)
        # to_response inherits these internal-only keys from to_dict:
        assert "created" in payload
        assert "alternative_profiles" in payload

        # The model has no such fields, so a round-trip drops them:
        dumped = MasteringRecommendationResponse(**payload).model_dump()
        assert "created" not in dumped
        assert "alternative_profiles" not in dumped

    def test_model_defaults_weighted_profiles_to_empty(self):
        from schemas import MasteringRecommendationResponse

        model = MasteringRecommendationResponse(
            track_id=1,
            primary_profile_id="warm",
            primary_profile_name="Warm",
            confidence_score=0.9,
            predicted_loudness_change=0.0,
            predicted_crest_change=0.0,
            predicted_centroid_change=0.0,
            is_hybrid=False,
        )
        assert model.weighted_profiles == []
        assert model.reasoning == ""
