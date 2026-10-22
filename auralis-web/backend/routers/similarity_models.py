"""
Similarity router request/response bodies (split from similarity.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.analysis.fingerprint import FingerprintNormalizer
from pydantic import BaseModel, Field


# Upper bound for `top_n` on the explain route. Derived from the dimension list
# the explanation actually slices — `DistanceCalculator.get_dimension_contributions()`
# enumerates `FingerprintNormalizer.DIMENSION_NAMES` — rather than hard-coded to
# today's count, so extending the fingerprint vector cannot leave the API
# silently refusing dimensions that exist (#4630).
EXPLAINABLE_DIMENSIONS = len(FingerprintNormalizer.DIMENSION_NAMES)


class FitSimilarityResponse(BaseModel):
    """Result of fitting the similarity system.

    Returned unchanged when the system was already fitted — `fitted` is True
    in both branches; only `message` distinguishes them.
    """
    fitted: bool = Field(description="True once the system is fitted")
    total_fingerprints: int = Field(description="Fingerprints the system was fitted on")
    message: str = Field(description="Human-readable summary")


# Response models
class SimilarTrack(BaseModel):
    """Similar track response model"""
    track_id: int = Field(..., description="ID of the similar track")
    distance: float = Field(..., description="Fingerprint distance (lower = more similar)")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score 0-1 (higher = more similar)")
    rank: int | None = Field(None, description="Rank in similarity (1=most similar)")

    # Optional track details
    title: str | None = None
    artist: str | None = None
    album: str | None = None


class ComparisonResult(BaseModel):
    """Pairwise comparison of two specific tracks."""
    track_id1: int = Field(..., description="First track ID")
    track_id2: int = Field(..., description="Second track ID")
    distance: float = Field(..., description="Fingerprint distance (lower = more similar)")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score 0-1")


class DimensionContribution(BaseModel):
    """A single fingerprint dimension's contribution to the distance.

    value1/value2/difference are the raw (denormalized) per-track values and
    are optional so a partial engine payload never fails validation (#4415).
    """
    dimension: str
    contribution: float
    value1: float | None = None
    value2: float | None = None
    difference: float | None = None


class SimilarityExplanation(BaseModel):
    """Detailed similarity explanation"""
    track_id1: int
    track_id2: int
    distance: float
    similarity_score: float
    # Both are arrays of DimensionContribution (#4415/#4416): top_differences
    # is the top-N by contribution, all_contributions is every dimension.
    top_differences: list[DimensionContribution]
    all_contributions: list[DimensionContribution]
