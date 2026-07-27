"""
Regression tests: ContentAnalysisFacade singleton and lazy builds are locked (#4549)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`get_content_analysis_facade()` was an unlocked check-then-create module-level
singleton, and the two lazy sub-analyzer properties on the shared instance
repeated the same shape. `reset()` nulled both from any thread with no lock, so
one thread could hold a reference to a ContentAnalyzer the facade no longer
owned while another built a replacement — two divergent stateful analyzers
producing inconsistent content classification.

All three module-level singleton accessors in the tree now use the same
double-checked pattern; this one was the only unlocked member of the family
(`get_parallel_processor` #2314, `get_processor_factory`,
`get_mastering_target_service`).

NOTE: this code has no production callers today — `get_content_analysis_facade`
is referenced only from its own module. These tests exercise the accessor
directly rather than through a call site, because no call site exists.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from __future__ import annotations

import threading

import pytest

from auralis.core.analysis import content_analysis_facade as facade_mod
from auralis.core.analysis.content_analysis_facade import (
    ContentAnalysisFacade,
    get_content_analysis_facade,
)

THREADS = 12


@pytest.fixture(autouse=True)
def _clear_singleton():
    """Each test starts from a cold process state."""
    facade_mod._global_content_analysis_facade = None
    yield
    facade_mod._global_content_analysis_facade = None


def _run_on_barrier(fn, threads: int = THREADS):
    """Fire `threads` workers simultaneously and collect (results, errors)."""
    barrier = threading.Barrier(threads)
    results: list = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker():
        try:
            barrier.wait(timeout=10)
            value = fn()
            with lock:
                results.append(value)
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    workers = [threading.Thread(target=worker) for _ in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=15)

    return results, errors


class TestSingletonAccessor:
    def test_concurrent_first_touch_constructs_once(self, monkeypatch):
        constructions = []
        real_init = ContentAnalysisFacade.__init__

        def counting_init(self, *args, **kwargs):
            constructions.append(1)
            real_init(self, *args, **kwargs)

        monkeypatch.setattr(ContentAnalysisFacade, "__init__", counting_init)

        results, errors = _run_on_barrier(get_content_analysis_facade)

        assert not errors, f"concurrent accessor raised: {errors}"
        assert len(results) == THREADS
        assert len({id(r) for r in results}) == 1, "threads got different instances"
        assert sum(constructions) == 1, (
            f"ContentAnalysisFacade constructed {sum(constructions)} times under "
            "concurrent first touch — accessor is not locked (#4549)"
        )

    def test_accessor_uses_double_checked_locking(self):
        """White-box guard so the accessor cannot silently drop its lock."""
        import inspect

        source = inspect.getsource(get_content_analysis_facade)
        assert "_global_content_analysis_facade_lock" in source, (
            "get_content_analysis_facade must acquire its creation lock (#4549)"
        )


class TestLazySubAnalyzers:
    def test_content_analyzer_constructs_once(self):
        f = ContentAnalysisFacade(sample_rate=44100)
        results, errors = _run_on_barrier(lambda: f.content_analyzer)

        assert not errors, f"concurrent lazy build raised: {errors}"
        assert len({id(r) for r in results}) == 1, (
            "content_analyzer built more than one instance (#4549)"
        )

    def test_target_generator_constructs_once(self):
        f = ContentAnalysisFacade(sample_rate=44100)
        results, errors = _run_on_barrier(lambda: f.target_generator)

        assert not errors, f"concurrent lazy build raised: {errors}"
        assert len({id(r) for r in results}) == 1, (
            "target_generator built more than one instance (#4549)"
        )


class TestResetDoesNotRace:
    def test_reset_never_exposes_none(self):
        """A reset() loop must never let a reader observe None or raise."""
        f = ContentAnalysisFacade(sample_rate=44100)
        stop = threading.Event()
        errors: list[BaseException] = []

        def resetter():
            while not stop.is_set():
                try:
                    f.reset()
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
                    return

        def reader():
            for _ in range(300):
                try:
                    assert f.content_analyzer is not None
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
                    return

        r = threading.Thread(target=resetter)
        readers = [threading.Thread(target=reader) for _ in range(4)]
        r.start()
        for t in readers:
            t.start()
        for t in readers:
            t.join(timeout=15)
        stop.set()
        r.join(timeout=15)

        assert not errors, f"reset raced a lazy build: {errors[:3]}"

    def test_reset_takes_the_lock(self):
        import inspect

        source = inspect.getsource(ContentAnalysisFacade.reset)
        assert "_analyzer_lock" in source, (
            "reset() must hold _analyzer_lock so it cannot interleave with a "
            "lazy build (#4549)"
        )
