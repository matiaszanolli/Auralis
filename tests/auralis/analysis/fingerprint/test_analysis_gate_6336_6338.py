"""The analysis memory gate is fair, prioritised, cancellable and taken before decode.

#6336: ``AnalysisBudget.reserve`` admitted any waiter that fit, so a pool of small
background jobs kept a long track's reservation out indefinitely, and nothing could
interrupt the wait — a stream whose init timed out left a thread that later ran the
analysis for nobody.

#6338: ``compute_windowed_fingerprint`` decoded the whole track BEFORE reserving, so
every waiting worker held a full input buffer on top of the gate's bound, and a
worker blocked on the gate could not honour the queue's ``stop()``.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import pytest

from auralis.analysis.fingerprint import windowed_compute
from auralis.analysis.fingerprint.analysis_budget import AnalysisBudget, AnalysisCancelled

JOB_S = 0.02  # one background job's analysis time, scaled down


def _saturate(budget: AnalysisBudget, workers: int, minutes: float, stop: threading.Event):
    """Workers that loop on ``minutes``-sized jobs, keeping the gate near full."""

    def loop() -> None:
        while not stop.is_set():
            with budget.reserve(minutes):
                time.sleep(JOB_S)

    threads = [threading.Thread(target=loop, daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()
    return threads


def _admitted_within(budget: AnalysisBudget, minutes: float, timeout_s: float, **kw) -> bool:
    admitted = threading.Event()

    def probe() -> None:
        with budget.reserve(minutes, **kw):
            admitted.set()

    threading.Thread(target=probe, daemon=True).start()
    return admitted.wait(timeout_s)


@pytest.mark.parametrize("workers", [12, 24])
def test_long_job_is_not_starved_by_a_saturating_pool_of_small_ones(workers):
    """The audit probe: 12 min never got in within 20 s behind 4 min jobs."""
    budget = AnalysisBudget(capacity_minutes=40.0)
    stop = threading.Event()
    threads = _saturate(budget, workers, minutes=4.0, stop=stop)
    try:
        time.sleep(0.1)  # let the pool saturate
        assert _admitted_within(budget, 12.0, timeout_s=2.0)
    finally:
        stop.set()
        for t in threads:
            t.join(2.0)


def test_interactive_waiter_overtakes_earlier_background_waiters():
    budget = AnalysisBudget(capacity_minutes=10.0)
    order: list[str] = []
    hold = threading.Event()

    def holder() -> None:
        with budget.reserve(10.0):  # fills the gate
            hold.wait(5.0)

    def waiter(name: str, interactive: bool) -> None:
        with budget.reserve(10.0, interactive=interactive):
            order.append(name)

    threading.Thread(target=holder, daemon=True).start()
    time.sleep(0.05)
    threads = [threading.Thread(target=waiter, args=("background", False), daemon=True)]
    threads[0].start()
    time.sleep(0.05)  # the background waiter is queued first
    threads.append(threading.Thread(target=waiter, args=("interactive", True), daemon=True))
    threads[1].start()
    time.sleep(0.05)
    hold.set()
    for t in threads:
        t.join(2.0)

    assert order == ["interactive", "background"]


def test_should_stop_abandons_the_wait_without_admitting_and_unblocks_the_queue():
    budget = AnalysisBudget(capacity_minutes=10.0)
    stopped = threading.Event()
    outcome: list[str] = []

    with budget.reserve(10.0):  # gate full

        def cancelled_waiter() -> None:
            try:
                with budget.reserve(5.0, should_stop=stopped.is_set):
                    outcome.append("admitted")
            except AnalysisCancelled:
                outcome.append("cancelled")

        t = threading.Thread(target=cancelled_waiter, daemon=True)
        t.start()
        time.sleep(0.05)
        stopped.set()
        t.join(2.0)
        assert not t.is_alive()

    assert outcome == ["cancelled"]
    # The cancelled ticket left the queue: the next job is admitted at once.
    assert _admitted_within(budget, 5.0, timeout_s=1.0)


def test_nothing_running_admits_an_oversized_job_despite_float_residue():
    """Minutes added and removed in different orders need not sum back to 0.0."""
    budget = AnalysisBudget(capacity_minutes=1.0)
    with budget.reserve(0.1):
        with budget.reserve(0.2):
            pass
    assert budget._in_flight != 0.0  # IEEE residue: (0.1 + 0.2) - 0.2 - 0.1
    assert _admitted_within(budget, 50.0, timeout_s=1.0)  # the job count rules


def test_track_is_not_decoded_before_the_gate_admits_it(monkeypatch):
    """#6338: a waiting job holds no input buffer, and a stop returns None."""
    budget = AnalysisBudget(capacity_minutes=1.0)
    monkeypatch.setattr(windowed_compute, "analysis_budget", budget)
    decoded: list[Path] = []

    def fake_load(audio_path, audio=None, sr=None, *, total_s=None):
        decoded.append(audio_path)
        return audio, sr, []

    monkeypatch.setattr(windowed_compute, "load_track_audio", fake_load)
    preloaded = np.zeros((2, 22050 * 60), dtype=np.float32)  # one minute
    stopped = threading.Event()
    result: list[object] = []

    with budget.reserve(1.0):  # gate full
        t = threading.Thread(
            target=lambda: result.append(windowed_compute.compute_windowed_fingerprint(
                object(), Path("queued.flac"), preloaded, 22050, should_stop=stopped.is_set
            )),
            daemon=True,
        )
        t.start()
        time.sleep(0.1)
        assert decoded == []  # still waiting, nothing decoded
        stopped.set()
        t.join(2.0)

    assert result == [None]
    assert decoded == []
