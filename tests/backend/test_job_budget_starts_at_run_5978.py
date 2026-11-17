"""A job's DSP timeout starts when the call starts, not when it is queued (#5978).

A timed-out or cancelled DSP call cannot be stopped and keeps its job-pool thread. The
next job then queued behind it and was billed that wait against its own budget.
"""

import asyncio
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import executors  # noqa: E402
from core.job_budget import run_job_dsp  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest.fixture
def two_thread_job_pool(monkeypatch):
    pool = ThreadPoolExecutor(max_workers=2)
    monkeypatch.setattr(executors, "_job_executor", pool)
    yield pool
    pool.shutdown(wait=False, cancel_futures=True)


async def test_queueing_behind_orphaned_calls_is_not_billed_to_the_budget(two_thread_job_pool):
    release = threading.Event()
    loop = asyncio.get_running_loop()
    orphans = [loop.run_in_executor(two_thread_job_pool, release.wait, 10) for _ in range(2)]
    await asyncio.sleep(0.05)  # both pool threads are now occupied

    job = asyncio.create_task(run_job_dsp(0.3, lambda: "mastered"))
    await asyncio.sleep(0.6)  # twice the budget, spent queued
    release.set()

    assert await job == "mastered"
    await asyncio.gather(*orphans)


async def test_a_call_that_runs_past_the_budget_still_times_out(two_thread_job_pool):
    release = threading.Event()
    try:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            await run_job_dsp(0.2, release.wait, 10)
        assert time.monotonic() - started < 2.0
    finally:
        release.set()


async def test_cancelling_a_queued_call_withdraws_it(two_thread_job_pool):
    release = threading.Event()
    ran = threading.Event()
    loop = asyncio.get_running_loop()
    orphans = [loop.run_in_executor(two_thread_job_pool, release.wait, 10) for _ in range(2)]
    await asyncio.sleep(0.05)

    job = asyncio.create_task(run_job_dsp(5, ran.set))
    await asyncio.sleep(0.05)
    job.cancel()
    with pytest.raises(asyncio.CancelledError):
        await job
    release.set()
    await asyncio.gather(*orphans)
    await asyncio.sleep(0.1)

    assert not ran.is_set()


async def test_a_function_error_propagates(two_thread_job_pool):
    def boom():
        raise ValueError("dsp failed")

    with pytest.raises(ValueError, match="dsp failed"):
        await run_job_dsp(1, boom)
