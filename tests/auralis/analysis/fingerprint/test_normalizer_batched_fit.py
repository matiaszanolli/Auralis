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

import threading

import numpy as np
import pytest

import auralis.analysis.fingerprint.normalizer as normalizer_module
from auralis.analysis.fingerprint.normalizer import (
    DimensionStats,
    FingerprintNormalizer,
)


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


def test_stop_event_set_before_first_batch_aborts_immediately(dims):
    """#4682: a stop_event set before fit() starts reading batches must abort
    with no batch reads at all — the cooperative-cancellation entry point a
    background caller (SimilarityAutoFitWorker) uses since the underlying
    thread can't be forcibly killed once a batch read is in flight."""
    repo = _FakeFingerprintRepository(_synthetic_vectors(130, dims))
    stop_event = threading.Event()
    stop_event.set()

    result = FingerprintNormalizer().fit(repo, min_samples=10, batch_size=50, stop_event=stop_event)

    assert result is False
    assert repo.get_all_calls == [], "must not read any batch once already stopped"


def test_stop_event_set_mid_fit_aborts_before_remaining_batches(dims):
    """A stop_event set partway through must stop the loop at the NEXT batch
    boundary rather than reading the whole table regardless."""
    repo = _FakeFingerprintRepository(_synthetic_vectors(300, dims))
    stop_event = threading.Event()

    # Set the event after the first batch read completes, simulating a
    # stop() call arriving mid-fit.
    real_get_all = repo.get_all

    def _get_all_then_stop(limit=None, offset=0):
        result = real_get_all(limit=limit, offset=offset)
        stop_event.set()
        return result

    repo.get_all = _get_all_then_stop

    result = FingerprintNormalizer().fit(repo, min_samples=10, batch_size=50, stop_event=stop_event)

    assert result is False
    assert len(repo.get_all_calls) == 1, "must not proceed past the batch where the stop was observed"


def test_fit_still_succeeds_when_stop_event_never_set(dims):
    """Passing a stop_event that is never set must not change fit()'s
    outcome — the parameter is purely additive."""
    vectors = _synthetic_vectors(130, dims)
    repo = _FakeFingerprintRepository(vectors)
    stop_event = threading.Event()

    result = FingerprintNormalizer().fit(repo, min_samples=10, batch_size=50, stop_event=stop_event)

    assert result is True


def test_fit_publishes_complete_stats_atomically(dims, monkeypatch):
    """Readers keep the previous complete model until all new stats exist."""
    vectors = _synthetic_vectors(20, dims)
    normalizer = FingerprintNormalizer()
    previous_stats = {
        name: DimensionStats(name, -100.0, 100.0, 0.0, 1.0, 10)
        for name in FingerprintNormalizer.DIMENSION_NAMES
    }
    normalizer.stats = previous_stats
    normalizer.fitted = True

    first_dimension_computed = threading.Event()
    release_fit = threading.Event()
    original_debug = normalizer_module.debug

    def blocking_debug(message):
        if not first_dimension_computed.is_set():
            first_dimension_computed.set()
            assert release_fit.wait(timeout=5)
        original_debug(message)

    monkeypatch.setattr(normalizer_module, "debug", blocking_debug)

    result: list[bool] = []
    fit_thread = threading.Thread(
        target=lambda: result.append(
            normalizer.fit(_FakeFingerprintRepository(vectors), min_samples=10)
        )
    )
    fit_thread.start()
    assert first_dimension_computed.wait(timeout=5)

    assert normalizer.stats is previous_stats
    assert normalizer.stats[FingerprintNormalizer.DIMENSION_NAMES[0]].min_val == -100.0

    release_fit.set()
    fit_thread.join(timeout=5)
    assert not fit_thread.is_alive()
    assert result == [True]
    assert set(normalizer.stats) == set(FingerprintNormalizer.DIMENSION_NAMES)
