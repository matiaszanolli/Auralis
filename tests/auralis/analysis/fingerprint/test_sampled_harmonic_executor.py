"""
Regression test: SampledHarmonicAnalyzer reuses a long-lived executor (#4118)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

_analyze_impl() used to build a fresh ThreadPoolExecutor(max_workers=4) per call
and shut it down with wait=False, so workers could outlive the handle on the
exception path and per-call creation churned threads under scan load. It now
reuses a single per-instance executor (joined in close()) and assembles results
defensively so a missing index can't raise mid-flight.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import threading

import numpy as np
import pytest

from auralis.analysis.fingerprint.analyzers.batch.harmonic_sampled import (
    SampledHarmonicAnalyzer,
)


def _audio(seconds: float, sr: int = 22050) -> np.ndarray:
    """Mono signal long enough to be split into several chunks."""
    n = int(sr * seconds)
    t = np.arange(n) / sr
    return (0.2 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)


@pytest.fixture
def analyzer():
    a = SampledHarmonicAnalyzer(chunk_duration=2.0, interval_duration=4.0)
    yield a
    a.close()


def test_executor_reused_across_calls(analyzer):
    """The same executor instance serves every call (no per-call creation)."""
    audio = _audio(30.0)
    analyzer._analyze_impl(audio, 22050)
    first = analyzer._get_executor()
    analyzer._analyze_impl(audio, 22050)
    second = analyzer._get_executor()
    assert first is second


def test_thread_count_bounded_over_many_calls(analyzer):
    """Repeated calls must not accumulate threads (bounded pool)."""
    audio = _audio(40.0)
    analyzer._analyze_impl(audio, 22050)  # warm up the pool
    baseline = threading.active_count()

    for _ in range(20):
        analyzer._analyze_impl(audio, 22050)

    # The shared 4-worker pool means active threads stay near baseline; a
    # per-call executor would spike with each call.
    assert threading.active_count() <= baseline + 4


def test_failing_chunk_degrades_without_leaking_threads(analyzer, monkeypatch):
    """A chunk that raises yields defaults, propagates nothing, leaks no threads."""
    def boom(chunk, sr, idx):
        raise RuntimeError("synthetic chunk failure")

    monkeypatch.setattr(analyzer, "_analyze_chunk", boom)
    audio = _audio(30.0)
    analyzer._analyze_impl(audio, 22050)  # create pool
    baseline = threading.active_count()

    # Many failing calls: a per-call executor with wait=False would accumulate
    # workers; the shared bounded pool keeps the count within its 4-worker cap.
    for _ in range(15):
        result = analyzer._analyze_impl(audio, 22050)  # all chunks fail
        # No exception; defaults returned for the 3 harmonic features.
        assert set(result.keys()) == {"harmonic_ratio", "pitch_stability", "chroma_energy"}

    assert threading.active_count() <= baseline + 4


def test_close_shuts_down_and_reinits():
    a = SampledHarmonicAnalyzer(chunk_duration=2.0, interval_duration=4.0)
    a._analyze_impl(_audio(20.0), 22050)
    assert a._executor is not None

    a.close()
    assert a._executor is None

    # Re-initialises on next use.
    a._analyze_impl(_audio(20.0), 22050)
    assert a._executor is not None
    a.close()
