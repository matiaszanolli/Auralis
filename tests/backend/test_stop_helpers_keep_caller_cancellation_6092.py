"""
Regression tests: stop/teardown helpers keep the caller's own cancellation (#6092).

``task.cancel(); try: await task; except CancelledError: pass`` cannot tell the
worker finishing its cancellation from the *caller* being cancelled while parked
on that await, so a cancelled request / second shutdown cancel ran on into the
steps it was told to abandon. Each site awaits a worker that unwinds slowly; the
caller is cancelled during that unwind and must see CancelledError.
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.job_worker import JobWorker
from core.position_ticker import PositionTickerMixin
from core.streamlined_lifecycle import WorkerLifecycleMixin
from core.task_cancellation import await_cancelled_task, caller_is_being_cancelled
from services.library_auto_scanner import LibraryAutoScanner


def _slow_unwinding_worker() -> "asyncio.Task[None]":
    """A task that handles its cancellation but takes a while to finish unwinding."""

    async def _work() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(0.3)

    return asyncio.ensure_future(_work())


async def _assert_cancelling_the_caller_propagates(stop_coro_factory) -> None:
    caller = asyncio.ensure_future(stop_coro_factory())
    await asyncio.sleep(0.05)  # caller is now parked awaiting the worker's unwind
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller


async def _assert_normal_stop_returns(stop_coro_factory) -> None:
    await asyncio.wait_for(stop_coro_factory(), timeout=5)


class _Ticker(PositionTickerMixin):
    def __init__(self, task) -> None:
        self._position_update_task = task


class _Lifecycle(WorkerLifecycleMixin):
    def __init__(self, task) -> None:
        self.running = True
        self._worker_task = task


def _job_worker(task) -> JobWorker:
    engine = SimpleNamespace(jobs={}, completed_job_ttl_hours=1, cleanup_old_jobs=AsyncMock())
    worker = JobWorker(engine, max_concurrent_jobs=1, max_queue_size=1)
    worker._worker_task = task
    return worker


def _auto_scanner(task) -> LibraryAutoScanner:
    scanner = LibraryAutoScanner(
        settings_repo=MagicMock(), library_database=MagicMock(),
        fingerprint_queue=None, connection_manager=MagicMock(),
    )
    scanner._task = task
    return scanner


SITES = {
    "position_ticker": lambda task: (lambda: _Ticker(task)._stop_position_updates()),
    "streamlined_lifecycle": lambda task: (lambda: _Lifecycle(task).stop()),
    "job_worker": lambda task: (lambda: _job_worker(task).stop()),
    "library_auto_scanner": lambda task: (lambda: _auto_scanner(task).stop()),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("site", SITES)
async def test_caller_cancellation_propagates_out_of_the_stop_helper(site):
    worker = _slow_unwinding_worker()
    await asyncio.sleep(0)  # let it start waiting
    await _assert_cancelling_the_caller_propagates(SITES[site](worker))


@pytest.mark.asyncio
@pytest.mark.parametrize("site", SITES)
async def test_normal_stop_still_returns(site):
    worker = _slow_unwinding_worker()
    await asyncio.sleep(0)
    await _assert_normal_stop_returns(SITES[site](worker))
    assert worker.done()


@pytest.mark.asyncio
async def test_helper_swallows_the_workers_own_teardown_exception():
    async def _boom() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise RuntimeError("teardown failed")

    task = asyncio.ensure_future(_boom())
    await asyncio.sleep(0)
    task.cancel()

    await await_cancelled_task(task)  # must not raise


@pytest.mark.asyncio
async def test_caller_is_being_cancelled_is_false_in_a_plain_callback():
    seen: list[bool] = []
    done = asyncio.Event()

    def _callback() -> None:  # runs on the loop but not inside any Task
        seen.append(caller_is_being_cancelled())
        done.set()

    asyncio.get_running_loop().call_soon(_callback)
    await asyncio.wait_for(done.wait(), timeout=5)

    assert seen == [False]
