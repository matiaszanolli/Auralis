"""A library reset unfits the similarity system instead of keeping the deleted library's model (#6584).

``fit()`` returns early while ``fitted and not needs_refit()``, and ``needs_refit()`` only fires once
the library grows to 1.5x the fitted sample - so after a reset to an empty (or smaller) library the
old ranges and calibration distance stayed in force until a restart.
"""

import numpy as np

from auralis.analysis.fingerprint import FingerprintSimilarity
from auralis.analysis.fingerprint.similarity_calibration import DEFAULT_REFERENCE_DISTANCE


class _Fingerprint:
    def __init__(self, fp_id: int, vector: np.ndarray):
        self.id = self.track_id = fp_id
        self._vector = vector

    def to_vector(self):
        return self._vector


class _Repo:
    """A fingerprint table the test can swap, as a reset plus rescan does."""

    def __init__(self, vectors: np.ndarray):
        self.rows = [_Fingerprint(i + 1, v) for i, v in enumerate(vectors)]

    def get_count(self, current_only=False):
        return len(self.rows)

    def get_batch_after_id(self, last_id, batch_size):
        return [fp for fp in self.rows if fp.id > last_id][:batch_size]

    def get_all(self, limit=None):
        return self.rows[:limit]


def _library(count: int, low: float, high: float, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).uniform(low, high, size=(count, 25))


def test_reset_forgets_the_model_and_the_next_fit_uses_the_new_library():
    repo = _Repo(_library(300, 0.0, 1.0, seed=1))
    system = FingerprintSimilarity(repo)
    assert system.fit(min_samples=10) is True
    old_stats = system.normalizer.stats

    system.reset()

    assert system.is_fitted() is False
    assert system.normalizer.is_fitted() is False
    assert system.normalizer.stats == {}
    assert system.fitted_model == ({}, DEFAULT_REFERENCE_DISTANCE)

    # A smaller, differently-shaped library: far below 1.5x the old sample, so without the reset
    # fit() would have returned early with the old ranges.
    repo.rows = _Repo(_library(40, 5.0, 6.0, seed=2)).rows
    assert system.fit(min_samples=10) is True
    new_stats = system.normalizer.stats
    assert new_stats is not old_stats
    first = next(iter(new_stats.values()))
    assert first.count == 40
    assert 5.0 <= first.min_val < first.max_val <= 6.0
    assert system.fitted_model[0] is new_stats


def test_reset_on_an_empty_library_stays_unfitted():
    repo = _Repo(_library(300, 0.0, 1.0, seed=1))
    system = FingerprintSimilarity(repo)
    system.fit(min_samples=10)

    system.reset()
    repo.rows = []

    assert system.fit(min_samples=10) is False
    assert system.is_fitted() is False
