"""
Regression test: FingerprintNormalizer.fit() batched reads (#4115)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

fit() used to load the entire track_fingerprints table as ORM objects via
get_all() (no limit) and build a dense N x 25 array alongside it. It now reads
in bounded batches via get_all(limit, offset), retaining only the compact
numeric vectors, so peak ORM memory is O(batch_size). The resulting statistics
must be numerically identical to the previous full-table computation, and
independent of the batch size.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint.normalizer import FingerprintNormalizer


class _FakeFingerprint:
    """Minimal stand-in exposing to_vector() like TrackFingerprint."""

    def __init__(self, vector):
        self._vector = list(vector)

    def to_vector(self):
        return list(self._vector)


class _FakeFingerprintRepository:
    """In-memory repo implementing the get_count / get_all(limit, offset) API."""

    def __init__(self, vectors):
        self._fps = [_FakeFingerprint(v) for v in vectors]
        self.get_all_calls = []

    def get_count(self):
        return len(self._fps)

    def get_all(self, limit=None, offset=0):
        self.get_all_calls.append((limit, offset))
        if limit is None:
            return list(self._fps)
        return self._fps[offset:offset + limit]


def _synthetic_vectors(n, dims, seed=1234):
    rng = np.random.default_rng(seed)
    # Spread of magnitudes across dims, mirroring real 25D fingerprints.
    return rng.uniform(-30.0, 200.0, size=(n, dims))


def _reference_stats(vectors, percentile_range=(5.0, 95.0)):
    """Stats computed exactly as the original full-array fit() did."""
    ref = {}
    for i in range(vectors.shape[1]):
        col = vectors[:, i]
        ref[i] = (
            float(np.percentile(col, percentile_range[0])),
            float(np.percentile(col, percentile_range[1])),
            float(np.mean(col)),
            float(np.std(col)),
        )
    return ref


@pytest.fixture
def dims():
    return len(FingerprintNormalizer.DIMENSION_NAMES)


def test_min_samples_short_circuit_returns_false(dims):
    repo = _FakeFingerprintRepository(_synthetic_vectors(5, dims))
    normalizer = FingerprintNormalizer()

    assert normalizer.fit(repo, min_samples=10) is False
    assert normalizer.fitted is False
    # Short-circuited on get_count() without reading rows.
    assert repo.get_all_calls == []


def test_batched_fit_matches_full_computation(dims):
    vectors = _synthetic_vectors(523, dims)
    ref = _reference_stats(vectors)

    repo = _FakeFingerprintRepository(vectors)
    normalizer = FingerprintNormalizer(use_robust=True)
    assert normalizer.fit(repo, min_samples=10, batch_size=50) is True
    assert normalizer.fitted is True

    for i, name in enumerate(FingerprintNormalizer.DIMENSION_NAMES):
        stats = normalizer.stats[name]
        exp_min, exp_max, exp_mean, exp_std = ref[i]
        assert stats.min_val == pytest.approx(exp_min, rel=1e-9, abs=1e-9)
        assert stats.max_val == pytest.approx(exp_max, rel=1e-9, abs=1e-9)
        assert stats.mean == pytest.approx(exp_mean, rel=1e-9, abs=1e-9)
        assert stats.std == pytest.approx(exp_std, rel=1e-9, abs=1e-9)
        assert stats.count == 523


def test_batch_size_does_not_change_results(dims):
    vectors = _synthetic_vectors(200, dims)

    def fit_with(batch_size):
        norm = FingerprintNormalizer(use_robust=True)
        norm.fit(_FakeFingerprintRepository(vectors), min_samples=10, batch_size=batch_size)
        return {n: (s.min_val, s.max_val, s.mean, s.std) for n, s in norm.stats.items()}

    small = fit_with(7)        # many batches, uneven final batch
    one_shot = fit_with(100000)  # single batch

    for name in FingerprintNormalizer.DIMENSION_NAMES:
        for a, b in zip(small[name], one_shot[name]):
            assert a == pytest.approx(b, rel=1e-12, abs=1e-12)


def test_non_robust_uses_absolute_min_max(dims):
    vectors = _synthetic_vectors(120, dims)
    repo = _FakeFingerprintRepository(vectors)
    normalizer = FingerprintNormalizer(use_robust=False)
    assert normalizer.fit(repo, min_samples=10, batch_size=16) is True

    for i, name in enumerate(FingerprintNormalizer.DIMENSION_NAMES):
        col = vectors[:, i]
        assert normalizer.stats[name].min_val == pytest.approx(float(np.min(col)))
        assert normalizer.stats[name].max_val == pytest.approx(float(np.max(col)))


def test_does_not_call_unbounded_get_all(dims):
    """fit() must page with a limit, never call get_all() unbounded (#4115)."""
    repo = _FakeFingerprintRepository(_synthetic_vectors(130, dims))
    FingerprintNormalizer().fit(repo, min_samples=10, batch_size=50)

    assert repo.get_all_calls, "expected paged get_all calls"
    assert all(limit is not None for limit, _offset in repo.get_all_calls)
