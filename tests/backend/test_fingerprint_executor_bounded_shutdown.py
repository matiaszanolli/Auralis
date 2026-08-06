"""
Regression: fingerprint ThreadPoolExecutor bounded-wait shutdown (#4756)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

shutdown_fingerprint_executor_bounded() is the lifespan-facing counterpart
to shutdown_fingerprint_executor() (the atexit safety net): it actually
waits (wait=True) for in-flight work so it cannot race the library-database
shutdown that follows it, but bounded by a timeout — offloaded via
asyncio.to_thread so the event loop stays responsive — so a pathologically
slow computation cannot stall process shutdown indefinitely.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from analysis import fingerprint_generator as fg

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _reset_executor():
    """The executor is a module-level singleton — make sure a stray one
    left by another test doesn't leak into or out of these tests."""
    fg.shutdown_fingerprint_executor()
    yield
    fg.shutdown_fingerprint_executor()


class TestNoExecutorIsANoOp:
    async def test_returns_immediately_when_no_executor_exists(self):
        assert fg._fingerprint_executor is None
        await fg.shutdown_fingerprint_executor_bounded()  # must not raise
        assert fg._fingerprint_executor is None


class TestGracefulShutdown:
    async def test_shuts_down_with_wait_true_and_clears_singleton(self):
        executor = fg._get_fingerprint_executor()
        assert fg._fingerprint_executor is executor

        with patch.object(executor, "shutdown", wraps=executor.shutdown) as mock_shutdown:
            await fg.shutdown_fingerprint_executor_bounded()

        mock_shutdown.assert_called_once_with(wait=True, cancel_futures=True)
        assert fg._fingerprint_executor is None

    async def test_completed_work_is_not_lost(self):
        """A quick, already-in-flight task must complete before shutdown
        returns — proving wait=True, not the atexit path's wait=False."""
        executor = fg._get_fingerprint_executor()
        results: list[int] = []
        future = executor.submit(lambda: results.append(1))
        future.result(timeout=5)  # let it finish before shutdown is even called

        await fg.shutdown_fingerprint_executor_bounded()

        assert results == [1]


class TestBoundedWait:
    async def test_timeout_does_not_raise_and_clears_singleton(self):
        """If the underlying shutdown(wait=True) exceeds the bound, the
        bounded wrapper must swallow the TimeoutError (log a warning, not
        propagate) — a stalled fingerprint computation must not prevent the
        rest of the lifespan's shutdown steps (the library database step in
        particular) from running."""
        executor = fg._get_fingerprint_executor()

        def _slow_shutdown(*args, **kwargs):
            import time
            time.sleep(0.5)

        with patch.object(executor, "shutdown", side_effect=_slow_shutdown):
            # Should NOT raise asyncio.TimeoutError despite the bound being
            # far shorter than the (fake) slow shutdown call.
            await fg.shutdown_fingerprint_executor_bounded(timeout=0.05)

        # The singleton is cleared before the bounded wait even starts, so a
        # timeout can't leave a half-torn-down executor referenced.
        assert fg._fingerprint_executor is None

    async def test_bounded_wait_uses_asyncio_to_thread(self):
        """The blocking shutdown(wait=True) call must be offloaded, not run
        directly on the event loop — otherwise the 'bounded' timeout can't
        actually interrupt anything, since asyncio.wait_for cannot cancel a
        synchronous call running inline on the same task."""
        executor = fg._get_fingerprint_executor()
        loop_was_blocked = False

        def _blocking_shutdown(*args, **kwargs):
            nonlocal loop_was_blocked
            import time
            time.sleep(0.2)

        async def _ticker():
            nonlocal loop_was_blocked
            # If shutdown() ran inline on the event loop, this sleep would
            # never get a chance to run concurrently with it.
            await asyncio.sleep(0.01)
            loop_was_blocked = False  # reached — loop was NOT blocked

        with patch.object(executor, "shutdown", side_effect=_blocking_shutdown):
            loop_was_blocked = True
            await asyncio.gather(
                fg.shutdown_fingerprint_executor_bounded(timeout=5.0),
                _ticker(),
            )

        assert loop_was_blocked is False, (
            "shutdown(wait=True) must run via asyncio.to_thread, not inline "
            "on the event loop"
        )
