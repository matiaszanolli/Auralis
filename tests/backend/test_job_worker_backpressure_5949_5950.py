"""JobWorker backpressure and shutdown (#5949, #5950).

The dispatcher used to pop each job from the bounded queue and immediately spawn
a task that parked on the concurrency semaphore. The queue therefore never
filled (QueueFull / HTTP 503 was unreachable, the backlog was an unbounded pile
of parked tasks), and stop() - which only cancelled tasks that had *taken* a slot
- left those parked tasks to start running as the cancelled jobs released their
slots, during and after shutdown.

These tests drive the real ProcessingEngine/JobWorker with a slow process_job.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.processing_engine import ProcessingEngine, ProcessingJob, ProcessingStatus

MAX_CONCURRENT = 2
MAX_QUEUE = 3


class _Harness:
    def __init__(self) -> None:
        store = MagicMock()
        store.forget = AsyncMock()
        store.save = AsyncMock()
        self.engine = ProcessingEngine(
            max_concurrent_jobs=MAX_CONCURRENT, max_queue_size=MAX_QUEUE, job_store=store
        )
        self.started: list[str] = []
        self.gate = asyncio.Event()
        self.engine.process_job = self._process_job  # type: ignore[method-assign]
        self.worker_task: asyncio.Task | None = None

    async def _process_job(self, job: ProcessingJob) -> None:
        self.started.append(job.job_id)
        job.status = ProcessingStatus.PROCESSING
        await self.gate.wait()
        job.status = ProcessingStatus.COMPLETED

    async def start(self) -> None:
        self.worker_task = asyncio.create_task(self.engine.start_worker())
        await asyncio.sleep(0)

    def make_job(self, n: int) -> ProcessingJob:
        job = ProcessingJob(
            job_id=f"job-{n}", input_path="/fake/in.wav", output_path="/fake/out.wav",
            settings={}, mode="adaptive",
        )
        self.engine.jobs[job.job_id] = job
        return job

    async def submit(self, n: int) -> ProcessingJob:
        job = self.make_job(n)
        await self.engine.submit_job(job)
        await asyncio.sleep(0.01)  # let the dispatcher run
        return job


@pytest.fixture
async def harness():
    h = _Harness()
    await h.start()
    yield h
    h.gate.set()
    await h.engine.stop_worker()


@pytest.mark.regression
@pytest.mark.asyncio
class TestQueueBackpressure5949:
    async def test_submission_past_capacity_raises_queue_full(self, harness):
        # 2 running + 3 queued is the capacity; the next one must be refused.
        for n in range(MAX_CONCURRENT + MAX_QUEUE):
            await harness.submit(n)

        with pytest.raises(asyncio.QueueFull):
            await harness.submit(99)

        assert "job-99" not in harness.engine.jobs  # a refused job leaves no trace

    async def test_only_the_concurrency_limit_runs_and_the_rest_wait_in_the_queue(self, harness):
        for n in range(MAX_CONCURRENT + MAX_QUEUE):
            await harness.submit(n)

        assert harness.started == ["job-0", "job-1"]
        status = harness.engine.get_queue_status()
        assert status["processing"] == MAX_CONCURRENT
        assert harness.engine.job_queue.qsize() == MAX_QUEUE
        assert status["queue_full"] is True

    async def test_backlog_drains_in_order_as_slots_free(self, harness):
        jobs = [await harness.submit(n) for n in range(MAX_CONCURRENT + MAX_QUEUE)]

        harness.gate.set()
        for _ in range(100):
            if all(j.status == ProcessingStatus.COMPLETED for j in jobs):
                break
            await asyncio.sleep(0.01)

        assert [j.status for j in jobs] == [ProcessingStatus.COMPLETED] * len(jobs)
        assert harness.started == [j.job_id for j in jobs]
        assert harness.engine.get_queue_status()["queue_full"] is False

    async def test_capacity_is_available_again_after_the_backlog_drains(self, harness):
        for n in range(MAX_CONCURRENT + MAX_QUEUE):
            await harness.submit(n)
        harness.gate.set()
        await asyncio.sleep(0.2)

        await harness.submit(100)  # must not raise


@pytest.mark.regression
@pytest.mark.asyncio
class TestShutdown5950:
    async def test_stop_runs_no_job_that_never_held_a_slot(self, harness):
        jobs = [await harness.submit(n) for n in range(MAX_CONCURRENT + MAX_QUEUE)]
        assert harness.started == ["job-0", "job-1"]

        await harness.engine.stop_worker()
        await asyncio.sleep(0.05)

        assert harness.started == ["job-0", "job-1"], "a waiting job started during/after shutdown"
        assert [j.status for j in jobs] == [ProcessingStatus.INTERRUPTED] * len(jobs)  # backend stop (#5994)
        alive = [t for t in asyncio.all_tasks() if (t.get_name() or "").startswith("_run_job")]
        assert not alive

    async def test_stop_returns_every_slot(self, harness):
        for n in range(MAX_CONCURRENT + MAX_QUEUE):
            await harness.submit(n)

        await harness.engine.stop_worker()

        assert harness.engine._concurrency_semaphore._value == MAX_CONCURRENT
        assert harness.engine._active_job_count == 0

    async def test_task_cancelled_before_its_first_step_returns_its_slot(self):
        # A worker that is not running, so no dispatcher is holding a slot of its own.
        h = _Harness()
        worker = h.engine._worker
        job = h.make_job(7)
        await worker._concurrency_semaphore.acquire()  # the slot the dispatcher handed over
        worker._unstarted.add(job.job_id)
        task = asyncio.create_task(worker._run_job(job, slot_held=True))
        worker._tasks[job.job_id] = task
        task.add_done_callback(lambda t: worker._on_job_task_done(job, t))

        task.cancel()  # before the task ever runs: its finally never executes
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)

        assert worker._concurrency_semaphore._value == MAX_CONCURRENT
        assert job.status == ProcessingStatus.CANCELLED
        assert job.job_id not in worker._tasks


@pytest.mark.regression
@pytest.mark.asyncio
class TestShutdownMarksJobsInterrupted5994:
    """A graceful stop() persisted in-flight and queued jobs as CANCELLED, so the
    INTERRUPTED state (and its message) was reachable only after a hard kill; a
    restart after a clean shutdown reported something different from one after a
    crash. Both now yield INTERRUPTED; a user's own cancel stays CANCELLED."""

    async def test_running_and_queued_jobs_are_interrupted_with_the_standard_message(self, harness):
        from core.job_store import INTERRUPTED_MESSAGE

        jobs = [await harness.submit(n) for n in range(MAX_CONCURRENT + MAX_QUEUE)]

        await harness.engine.stop_worker()

        assert {j.status for j in jobs} == {ProcessingStatus.INTERRUPTED}
        assert {j.error_message for j in jobs} == {INTERRUPTED_MESSAGE}
        assert all(j.completed_at is not None for j in jobs)

    async def test_every_interrupted_job_is_persisted_as_interrupted(self, harness, monkeypatch):
        from unittest.mock import AsyncMock

        # The harness injects a MagicMock store, which persist() deliberately skips
        # (only a real JobStore saves), so observe the persist calls themselves.
        persisted = AsyncMock()
        monkeypatch.setattr("core.job_worker.persist", persisted)
        jobs = [await harness.submit(n) for n in range(MAX_CONCURRENT + MAX_QUEUE)]

        await harness.engine.stop_worker()

        handed_over = {call.args[1].job_id: call.args[1].status for call in persisted.await_args_list}
        assert set(handed_over) == {j.job_id for j in jobs}, "a queued or running job was not persisted"
        assert set(handed_over.values()) == {ProcessingStatus.INTERRUPTED}

    async def test_a_users_cancel_is_still_cancelled(self, harness):
        jobs = [await harness.submit(n) for n in range(MAX_CONCURRENT + 1)]
        queued = jobs[-1]

        assert await harness.engine.cancel_job(queued.job_id) is True

        assert queued.status == ProcessingStatus.CANCELLED

