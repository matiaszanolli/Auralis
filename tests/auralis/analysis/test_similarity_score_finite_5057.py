"""
calculate_similarity_score must never return NaN — issue #5057
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`SimilarTrack.similarity_score` and `ComparisonResult.similarity_score` are
declared `Field(..., ge=0.0, le=1.0)` on RESPONSE models. On a request model that
bound usefully rejects NaN with a 422; on a response it does the opposite —
`nan >= 0.0` is False, so a NaN score fails validation at serialization and
FastAPI raises `ResponseValidationError`, handing the client an opaque 500
instead of a degenerate-but-valid payload.

`np.clip` inside `normalize_to_range` saturates ±inf but passes NaN straight
through, so NaN was the single value that escaped. Every similarity score in the
system comes from `calculate_similarity_score` — the real-time search, the
pairwise comparison, and the edges `KNNGraphBuilder` persists — so guarding it
there closes all three paths at once.
"""

from __future__ import annotations

import math

import pytest

from auralis.analysis.fingerprint.distance import FingerprintDistance


@pytest.fixture
def calc() -> FingerprintDistance:
    return FingerprintDistance()


class TestAlwaysFinite:
    """The invariant the response models assert but cannot enforce."""

    @pytest.mark.parametrize(
        "distance",
        [float("nan"), float("inf"), float("-inf"), -1e9, -1.0, 0.0, 0.5, 1.0, 2.0, 1e9],
    )
    def test_score_is_finite_and_in_range(self, calc, distance: float) -> None:
        score = calc.calculate_similarity_score(distance)

        assert math.isfinite(score), f"{distance!r} produced {score!r}"
        assert 0.0 <= score <= 1.0, f"{distance!r} produced {score!r}"

    @pytest.mark.parametrize("max_distance", [float("nan"), float("inf"), 0.0, 1e-12])
    def test_a_degenerate_max_distance_also_stays_finite(self, calc, max_distance: float) -> None:
        score = calc.calculate_similarity_score(0.5, max_distance)

        assert math.isfinite(score)
        assert 0.0 <= score <= 1.0

    def test_nan_distance_collapses_to_least_similar(self, calc) -> None:
        """The specific regression, and the numeric choice behind it.

        0.0 rather than a neutral 0.5: `find_similar` sorts by this score
        descending, so a pair that could not be measured must not outrank one
        that could.
        """
        assert calc.calculate_similarity_score(float("nan")) == 0.0

    def test_an_unmeasurable_pair_sorts_below_a_measured_dissimilar_one(self, calc) -> None:
        """Why 0.0 and not 0.5 — stated as the property it buys."""
        unmeasurable = calc.calculate_similarity_score(float("nan"))
        measured_but_distant = calc.calculate_similarity_score(0.95)

        assert unmeasurable <= measured_but_distant


class TestOrdinaryBehaviourUnchanged:
    """The guard must not perturb any distance that was already well-defined."""

    def test_identical_is_one_and_max_distance_is_zero(self, calc) -> None:
        assert calc.calculate_similarity_score(0.0) == 1.0
        assert calc.calculate_similarity_score(1.0) == 0.0

    def test_monotonically_decreasing_in_distance(self, calc) -> None:
        scores = [calc.calculate_similarity_score(d / 10) for d in range(11)]
        assert scores == sorted(scores, reverse=True)

    def test_infinities_still_saturate_rather_than_being_caught_by_the_guard(self, calc) -> None:
        """np.clip already handled these; the guard is for NaN alone."""
        assert calc.calculate_similarity_score(float("inf")) == 0.0
        assert calc.calculate_similarity_score(float("-inf")) == 1.0

    def test_out_of_range_distances_still_clip(self, calc) -> None:
        assert calc.calculate_similarity_score(-5.0) == 1.0
        assert calc.calculate_similarity_score(5.0) == 0.0


class TestResponseModelBoundsAreSatisfiable:
    """Pin the contract the router's `ge`/`le` fields declare.

    The bounds are kept rather than dropped: with the producer guaranteeing a
    finite in-range value they are a real invariant assertion, not a trap.
    """

    @pytest.mark.parametrize(
        "distance", [float("nan"), float("inf"), float("-inf"), -3.0, 0.25, 7.0]
    )
    def test_every_score_satisfies_ge_zero_le_one(self, calc, distance: float) -> None:
        score = calc.calculate_similarity_score(distance)

        # Exactly the comparisons pydantic performs for ge=0.0, le=1.0. Both are
        # False for NaN, which is how a NaN turned into a 500.
        assert score >= 0.0
        assert score <= 1.0
