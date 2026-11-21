"""The similarity score is scaled by the typical distance between unrelated tracks (#5923).

``1 - distance / 1.0`` made two unrelated tracks display as a ~60% match (rank 1 and rank 20
looked alike). fit() now measures the 95th-percentile pairwise distance of the library and uses it
as the 0% point.
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint import FingerprintSimilarity
from auralis.analysis.fingerprint.distance import FingerprintDistance
from auralis.analysis.fingerprint.similarity_calibration import (
    DEFAULT_REFERENCE_DISTANCE,
    calibrate_reference_distance,
    reference_distance_of,
)


class _Fingerprint:
    def __init__(self, track_id: int, vector: np.ndarray):
        self.track_id = track_id
        self._vector = vector

    def to_vector(self):
        return self._vector


class _Repo:
    def __init__(self, vectors: np.ndarray):
        self.fingerprints = [_Fingerprint(i, v) for i, v in enumerate(vectors)]

    def get_all(self, limit=None):
        return self.fingerprints[:limit]

    def get_by_track_id(self, track_id):
        return self.fingerprints[track_id]


class _Identity:
    def normalize(self, vector):
        return vector


def _library(count: int = 200, seed: int = 1) -> np.ndarray:
    return np.random.default_rng(seed).uniform(0.0, 1.0, size=(count, 25))  # independent uniform dims


def test_unrelated_tracks_no_longer_display_as_a_majority_match():
    vectors = _library()
    calc = FingerprintDistance()
    reference = reference_distance_of(calc, vectors)

    # The old scale: a typical unrelated pair (~0.4 distance) scored ~60%.
    typical = float(np.median(calc.calculate_batch(vectors[0], vectors[1:])))
    assert calc.calculate_similarity_score(typical) > 0.5
    assert calc.calculate_similarity_score(typical, reference) < 0.5  # a median-distance pair

    # An identical pair is still 100% and the 95th-percentile pair is the 0% point.
    assert calc.calculate_similarity_score(0.0, reference) == 1.0
    assert calc.calculate_similarity_score(reference, reference) == pytest.approx(0.0, abs=1e-6)


def test_scores_spread_across_ranks_instead_of_clustering():
    vectors = _library()
    calc = FingerprintDistance()
    reference = reference_distance_of(calc, vectors)
    distances = np.sort(calc.calculate_batch(vectors[0], vectors[1:]))

    old = [calc.calculate_similarity_score(float(d)) for d in (distances[0], distances[19])]
    new = [calc.calculate_similarity_score(float(d), reference) for d in (distances[0], distances[19])]

    assert (new[0] - new[1]) > (old[0] - old[1])  # rank 1 vs rank 20 now look different


def test_fit_stores_the_reference_and_find_similar_scores_with_it():
    vectors = _library(60)
    system = FingerprintSimilarity(_Repo(vectors))
    system.normalizer.normalize = lambda v, stats=None: v  # type: ignore[method-assign]
    system.normalizer.fit = lambda *a, **k: True  # type: ignore[method-assign]

    assert system.reference_distance == DEFAULT_REFERENCE_DISTANCE
    assert system.fit(min_samples=10) is True
    assert system.reference_distance != DEFAULT_REFERENCE_DISTANCE

    best = system.find_similar(0, n=1, use_prefilter=False)[0]
    expected = FingerprintDistance().calculate_similarity_score(best.distance, system.reference_distance)
    assert best.similarity_score == pytest.approx(expected)


def test_calibration_is_deterministic_and_never_raises():
    repo = _Repo(_library(80))

    first = calibrate_reference_distance(repo, _Identity(), FingerprintDistance())
    second = calibrate_reference_distance(repo, _Identity(), FingerprintDistance())
    assert first == second

    class _Broken:
        def get_all(self, limit=None):
            raise RuntimeError("db gone")

    assert calibrate_reference_distance(_Broken(), _Identity(), FingerprintDistance()) == DEFAULT_REFERENCE_DISTANCE
    assert calibrate_reference_distance(_Repo(_library(1)), _Identity(), FingerprintDistance()) == DEFAULT_REFERENCE_DISTANCE


def test_identical_library_falls_back_rather_than_dividing_by_zero():
    same = np.tile(np.full(25, 0.5), (20, 1))

    assert reference_distance_of(FingerprintDistance(), same) == DEFAULT_REFERENCE_DISTANCE
