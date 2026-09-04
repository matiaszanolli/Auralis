"""Regression coverage for concurrent similarity fitting (#5243)."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from auralis.analysis.fingerprint.similarity import FingerprintSimilarity


def test_concurrent_fit_reuses_the_first_completed_model(monkeypatch):
    """Startup and manual fit calls must not run the normalizer twice."""
    similarity = FingerprintSimilarity(fingerprint_repository=object())
    begin_fit = threading.Barrier(2)
    first_fit_started = threading.Event()
    release_first_fit = threading.Event()
    calls = 0
    calls_lock = threading.Lock()

    def slow_fit(*args, **kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
        first_fit_started.set()
        assert release_first_fit.wait(timeout=5)
        return True

    monkeypatch.setattr(similarity.normalizer, "fit", slow_fit)

    def fit_concurrently():
        begin_fit.wait(timeout=5)
        return similarity.fit()

    with ThreadPoolExecutor(max_workers=2) as executor:
        startup_fit = executor.submit(fit_concurrently)
        manual_fit = executor.submit(fit_concurrently)
        assert first_fit_started.wait(timeout=5)
        time.sleep(0.05)
        assert calls == 1
        release_first_fit.set()

        assert startup_fit.result(timeout=5) is True
        assert manual_fit.result(timeout=5) is True

    assert calls == 1
    assert similarity.is_fitted() is True
