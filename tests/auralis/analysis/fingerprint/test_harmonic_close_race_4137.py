"""
SampledHarmonicAnalyzer.close() must not race in-flight analyses (#4137).

close() previously could shut the executor down in the window between
_get_executor() returning and executor.submit(), raising "cannot schedule new
futures after shutdown" (swallowed as harmonic_ratio=0.5). close() now waits for
in-flight analyses via an active-analysis counter.
"""

import threading

import numpy as np
import pytest

from auralis.analysis.fingerprint.analyzers.batch.harmonic_sampled import (
    SampledHarmonicAnalyzer,
)


def test_close_waits_for_in_flight_analysis(monkeypatch):
    analyzer = SampledHarmonicAnalyzer()
    started = threading.Event()
    release = threading.Event()

    orig_chunk = analyzer._analyze_chunk

    def slow_chunk(chunk, sr, i):
        started.set()
        release.wait(timeout=5.0)
        return orig_chunk(chunk, sr, i)

    monkeypatch.setattr(analyzer, "_analyze_chunk", slow_chunk)

    sig = (np.random.RandomState(0).randn(44100 * 3) * 0.1).astype(np.float32)
    result = {}

    def run_analyze():
        result["r"] = analyzer.analyze(sig, 44100)

    t = threading.Thread(target=run_analyze)
    t.start()
    assert started.wait(timeout=5.0), "analysis never started"

    closed = threading.Event()

    def run_close():
        analyzer.close()
        closed.set()

    ct = threading.Thread(target=run_close)
    ct.start()

    # close() must block while the analysis is in flight.
    assert not closed.wait(timeout=0.5), "close() did not wait for in-flight analysis"

    # Let the analysis finish; close() should then complete and the result must
    # be a real computation, not the swallowed default.
    release.set()
    t.join(timeout=10.0)
    ct.join(timeout=10.0)

    assert closed.is_set()
    assert "harmonic_ratio" in result["r"]
