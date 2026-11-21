"""A similarity result always comes from ONE fitted model, even during a refit (#6573).

#5243 made a refit publish its statistics as one dict, but ``normalize()`` re-read ``self.stats``
for each of its 25 dimensions, so a refit landing mid-call normalised one vector with dimensions
from two models. And ``fit()`` made the new statistics live before it calibrated the reference
distance, so a score could pair the new ranges with the old scale - and a multi-vector call
(target plus candidates) could straddle the swap.
"""
import numpy as np

from auralis.analysis.fingerprint import FingerprintNormalizer, FingerprintSimilarity
from auralis.analysis.fingerprint.normalizer_stats import DimensionStats
from auralis.analysis.fingerprint.similarity_calibration import DEFAULT_REFERENCE_DISTANCE

NAMES = FingerprintNormalizer.DIMENSION_NAMES


def _model(low: float, high: float) -> dict[str, DimensionStats]:
    return {
        name: DimensionStats(name=name, min_val=low, max_val=high, mean=(low + high) / 2, std=1.0, count=10)
        for name in NAMES
    }


class _SwapsOnFirstRead(dict):
    """A published model whose first lookup publishes a new one - a refit landing mid-call."""

    def __init__(self, owner: FingerprintNormalizer, initial: dict, replacement: dict):
        super().__init__(initial)
        self._owner, self._replacement, self._swapped = owner, replacement, False

    def __getitem__(self, key):
        if not self._swapped:
            self._swapped = True
            self._owner.stats = self._replacement
        return super().__getitem__(key)


def test_normalize_uses_one_model_for_every_dimension_when_a_refit_lands_mid_call():
    normalizer = FingerprintNormalizer()
    normalizer.fitted = True
    first, second = _model(0.0, 10.0), _model(0.0, 100.0)
    normalizer.stats = _SwapsOnFirstRead(normalizer, first, second)
    vector = [5.0] * 25

    result = normalizer.normalize(vector)

    expected = FingerprintNormalizer()
    expected.fitted, expected.stats = True, first
    np.testing.assert_array_equal(result, expected.normalize(vector))
    assert len(set(result.tolist())) == 1  # every dimension from the same range


def test_a_pinned_model_is_used_instead_of_the_live_one():
    normalizer = FingerprintNormalizer()
    normalizer.fitted, normalizer.stats = True, _model(0.0, 100.0)

    assert normalizer.normalize([5.0] * 25, _model(0.0, 10.0))[0] == np.float32(0.5)


class _Fingerprint:
    def __init__(self, track_id: int, value: float):
        self.track_id = track_id
        self._vector = [value] * 25

    def to_vector(self):
        return self._vector


class _Repo:
    def __init__(self, count: int = 20):
        self.fingerprints = [_Fingerprint(i, float(i)) for i in range(count)]

    def get_all(self, limit=None):
        return self.fingerprints[:limit]

    def get_by_track_id(self, track_id):
        return self.fingerprints[track_id]

    def get_count(self, current_only=False):
        return len(self.fingerprints)


def _fitted_system(stats: dict, reference: float) -> FingerprintSimilarity:
    system = FingerprintSimilarity(_Repo())
    system.normalizer.fitted, system.normalizer.stats = True, stats
    system.fitted_model = (stats, reference)
    system.fitted = True
    return system


def test_fit_publishes_the_stats_and_their_reference_together(monkeypatch):
    system = FingerprintSimilarity(_Repo())
    old_model = system.fitted_model
    new_stats = _model(0.0, 20.0)
    seen_during_calibration = {}

    def fake_fit(*_a, **_k):
        system.normalizer.stats, system.normalizer.fitted = new_stats, True  # live before calibration
        return True

    def fake_calibrate(_repo, normalizer, _calc):
        seen_during_calibration["model"] = system.fitted_model
        seen_during_calibration["stats"] = normalizer.stats
        return 0.7

    monkeypatch.setattr(system.normalizer, "fit", fake_fit)
    monkeypatch.setattr("auralis.analysis.fingerprint.similarity.calibrate_reference_distance", fake_calibrate)

    assert system.fit(min_samples=1) is True

    assert seen_during_calibration["stats"] is new_stats  # calibrated against the new ranges ...
    assert seen_during_calibration["model"] is old_model  # ... while readers still saw the old pair
    assert system.fitted_model == (new_stats, 0.7)
    assert system.reference_distance == 0.7
    assert old_model == ({}, DEFAULT_REFERENCE_DISTANCE)


def test_find_similar_scores_every_candidate_with_the_model_it_started_with():
    pinned = _model(0.0, 20.0)
    system = _fitted_system(pinned, 0.5)
    seen: list = []
    live_normalize = system.normalizer.normalize

    def spying_normalize(vector, stats=None):
        seen.append(stats)
        if len(seen) == 1:  # a refit publishes right after the target is normalised
            system.fitted_model = (_model(0.0, 200.0), 9.9)
        return live_normalize(vector, stats)

    system.normalizer.normalize = spying_normalize  # type: ignore[method-assign]

    results = system.find_similar(0, n=3, use_prefilter=False)

    assert len(seen) > 2 and all(stats is pinned for stats in seen)
    distance = results[0].distance
    assert results[0].similarity_score == system.distance_calc.calculate_similarity_score(distance, 0.5)


def test_calculate_similarity_uses_one_pinned_model():
    pinned = _model(0.0, 20.0)
    system = _fitted_system(pinned, 0.5)
    seen: list = []
    live_normalize = system.normalizer.normalize

    def spying_normalize(vector, stats=None):
        seen.append(stats)
        system.fitted_model = (_model(0.0, 200.0), 9.9)  # refits keep landing
        return live_normalize(vector, stats)

    system.normalizer.normalize = spying_normalize  # type: ignore[method-assign]

    result = system.calculate_similarity(1, 2)

    assert seen == [pinned, pinned]
    assert result.similarity_score == system.distance_calc.calculate_similarity_score(result.distance, 0.5)
