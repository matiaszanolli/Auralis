"""
Regression tests: SimilarityAutoFitWorker (#4682)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The similarity auto-fit pass used to run on a bare `threading.Thread(daemon=
True)` — never stored, never joined, no stop signal. Lifespan shutdown had
no knowledge of it, so a quit during auto-fit tore the process down (and
disposed the SQLAlchemy engine) while the thread might still hold a session
against it; a library reset raced it reading fingerprints from a database
being wiped out from under it.

SimilarityAutoFitWorker gives it the same async start()/stop() shape as
every other BACKGROUND_WORKER_KEYS entry, with `fit()` cooperatively checking
a threading.Event between batches (see test_normalizer_batched_fit.py for
that half) since an in-flight batch read can't be forcibly cancelled.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.background_workers import BACKGROUND_WORKER_KEYS  # noqa: E402
from services.similarity_autofit_worker import SimilarityAutoFitWorker  # noqa: E402


def _make_worker(fit_side_effect):
    sim_system = MagicMock()
    sim_system.fit.side_effect = fit_side_effect
    lib_mgr = MagicMock()
    globals_dict: dict = {}
    builder_cls = MagicMock()
    worker = SimilarityAutoFitWorker(
        sim_system=sim_system, lib_mgr=lib_mgr, globals_dict=globals_dict, builder_cls=builder_cls
    )
    return worker, sim_system, lib_mgr, globals_dict, builder_cls


class TestWiring:
    def test_similarity_autofit_is_a_registered_background_worker(self):
        """#4682 WIRING check: the key must actually be registered so
        shutdown/reset/rollback (all derived from BACKGROUND_WORKER_KEYS)
        pick it up automatically."""
        assert "similarity_autofit" in BACKGROUND_WORKER_KEYS


class TestSuccessfulFit:
    async def test_start_populates_graph_builder_on_success(self):
        worker, sim_system, lib_mgr, globals_dict, builder_cls = _make_worker(
            fit_side_effect=lambda **kw: True
        )

        await worker.start()
        await worker.stop()  # awaits completion; fit already returned by now

        assert globals_dict["graph_builder"] is builder_cls.return_value
        builder_cls.assert_called_once_with(
            similarity_system=sim_system, session_factory=lib_mgr.SessionLocal
        )

    async def test_fit_returning_false_leaves_graph_builder_unset(self):
        """Not enough fingerprints yet — must not construct a graph builder."""
        worker, _sim, _lib, globals_dict, builder_cls = _make_worker(
            fit_side_effect=lambda **kw: False
        )

        await worker.start()
        await worker.stop()

        assert "graph_builder" not in globals_dict
        builder_cls.assert_not_called()

    async def test_fit_raising_is_swallowed_and_leaves_graph_builder_unset(self):
        def _boom(**kw):
            raise RuntimeError("db exploded")

        worker, _sim, _lib, globals_dict, builder_cls = _make_worker(fit_side_effect=_boom)

        await worker.start()
        await worker.stop()  # must not raise

        assert "graph_builder" not in globals_dict
        builder_cls.assert_not_called()


class TestStop:
    async def test_stop_sets_the_stop_event_fit_receives(self):
        """fit() must be called with the SAME Event stop() sets — otherwise
        the cooperative-cancel signal never reaches the batch loop."""
        observed_event: list = []

        def _fit(stop_event=None, **kw):
            observed_event.append(stop_event)
            return stop_event.wait(timeout=5)  # blocks until stop() sets it

        worker, *_ = _make_worker(fit_side_effect=_fit)

        await worker.start()
        await worker.stop()

        assert len(observed_event) == 1
        assert isinstance(observed_event[0], threading.Event)
        assert observed_event[0].is_set(), "stop() must have set the event fit() was given"

    async def test_stop_waits_for_the_thread_to_actually_exit(self):
        """A cancelled fit leaves graph_builder unset even if the underlying
        thread is still mid-flight when stop() is first called -- stop()
        must block until it genuinely finishes, not return immediately."""
        release = threading.Event()

        def _fit(stop_event=None, **kw):
            # Simulate real work that checks the event between "batches".
            for _ in range(50):
                if stop_event.is_set():
                    return False
                time.sleep(0.01)
            return False

        worker, _sim, _lib, globals_dict, builder_cls = _make_worker(fit_side_effect=_fit)

        await worker.start()
        await worker.stop()

        assert "graph_builder" not in globals_dict
        builder_cls.assert_not_called()

    async def test_stop_before_start_is_a_safe_no_op(self):
        worker, *_ = _make_worker(fit_side_effect=lambda **kw: True)
        await worker.stop()  # must not raise

    async def test_start_is_a_no_op_while_already_running(self):
        """A second start() while one fit is in flight must not spawn a
        second concurrent fit."""
        call_count = {"n": 0}
        release = threading.Event()

        def _fit(stop_event=None, **kw):
            call_count["n"] += 1
            release.wait(timeout=5)
            return True

        worker, *_ = _make_worker(fit_side_effect=_fit)

        await worker.start()
        await worker.start()  # should see the in-flight task and no-op

        release.set()
        await worker.stop()

        assert call_count["n"] == 1
