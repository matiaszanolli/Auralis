"""
Mastering Recommendation Schemas

Split out of schemas.py (#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pydantic import BaseModel, Field

# ============================================================================
# Mastering Recommendation
# ============================================================================


class WeightedProfileResponse(BaseModel):
    """A single profile and its weight in a blended (hybrid) recommendation."""
    profile_id: str = Field(description="Mastering profile identifier")
    profile_name: str = Field(description="Human-readable profile name")
    weight: float = Field(description="Blend weight (0–1, all weights sum to 1.0)")


class MasteringRecommendationResponse(BaseModel):
    """Mastering profile recommendation for a track.

    Mirrors the frontend ``MasteringRecommendationResponse`` (``api.ts``) so the
    REST endpoint honors the same contract as the WS broadcast. Declaring this
    as the endpoint's ``response_model`` also strips the internal-only
    ``created`` / ``alternative_profiles`` fields that ``to_dict()`` emits but
    no REST consumer expects (fixes #3840).
    """
    track_id: int = Field(description="Track database ID")
    primary_profile_id: str = Field(description="Best-matching profile identifier")
    primary_profile_name: str = Field(description="Best-matching profile name")
    confidence_score: float = Field(description="Recommendation confidence (0–1)")
    predicted_loudness_change: float = Field(description="Predicted RMS change (dB)")
    predicted_crest_change: float = Field(description="Predicted crest-factor change (dB)")
    predicted_centroid_change: float = Field(description="Predicted spectral-centroid change (Hz)")
    weighted_profiles: list[WeightedProfileResponse] = Field(
        default_factory=list,
        description="Blended profiles when hybrid; empty list otherwise",
    )
    reasoning: str = Field(default="", description="Explanation for the recommendation")
    is_hybrid: bool = Field(description="Whether this is a blended (weighted) recommendation")
