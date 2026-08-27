"""
Tests for background-worker task lifecycle hygiene (#4575, #4577)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``StreamlinedCacheWorker.stop()`` and ``JobWorker.stop()`` cancelled and
awaited their worker task but never cleared ``_worker_task``, leaving a stale
reference to a finished task. The startup health reporter reads that attribute,
so a probe landing between a stop and the next start would see a done task and
misreport worker health (#4577).

``JobWorker.cancel_task()`` documented itself as thread-safe while calling
``asyncio.Task.cancel()`` directly, which is only valid on the event-loop
thread — the docstring invited an unsafe call site (#4575).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import inspect
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.job_worker import JobWorker
from core.streamlined_worker import StreamlinedCacheWorker

pytestmark = pytest.mark.asyncio


@pytest.fixture
def worker() -> StreamlinedCacheWorker:
    """A worker whose loop does nothing but sleep."""
    return StreamlinedCacheWorker(cache_manager=MagicMock(), library_database=MagicMock())


class TestStreamlinedWorkerTaskReset:
    """#4577 — stop() must drop the finished task reference."""

    async def test_stop_clears_worker_task(self, worker):
        await worker.start()
        assert worker._worker_task is not None

        await worker.stop()

        assert worker._worker_task is None
        assert worker.running is False

    async def test_stop_start_leaves_exactly_one_live_task(self, worker):
        await worker.start()
        first = worker._worker_task
        await worker.stop()
        await worker.start()

        assert worker._worker_task is not first
        assert not worker._worker_task.done()
        assert first.done()

        await worker.stop()

    async def test_stop_is_idempotent(self, worker):
        await worker.start()
        await worker.stop()
        await worker.stop()  # must not raise on the now-None reference

        assert worker._worker_task is None


class TestStreamlinedWorkerIsRunning:
    """#4577 — public accessor is false in all three dead states."""

    async def test_false_before_start(self, worker):
        assert worker.is_running is False

    async def test_true_after_start(self, worker):
        await worker.start()
        try:
            assert worker.is_running is True
        finally:
            await worker.stop()

    async def test_false_after_stop(self, worker):
        await worker.start()
        await worker.stop()

        assert worker.is_running is False

    async def test_false_when_task_crashed(self, worker):
        """The #3898 case: a done-with-exception task must not read as running."""

        async def boom() -> None:
            raise RuntimeError("worker died")

        worker.running = True
        worker._worker_task = asyncio.get_running_loop().create_task(boom())
        await asyncio.sleep(0)  # let it die
        await asyncio.gather(worker._worker_task, return_exceptions=True)

        assert worker.is_running is False

    async def test_worker_task_accessor_matches_private_attribute(self, worker):
        assert worker.worker_task is None
        await worker.start()
        try:
            assert worker.worker_task is worker._worker_task
        finally:
            await worker.stop()

    def test_startup_health_reporter_uses_the_accessor(self):
        """#4577 WIRING: no external reader of the private attribute remains."""
        backend = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
        offenders = []
        for path in backend.rglob("*.py"):
            if path.name in ("streamlined_worker.py", "job_worker.py", "fingerprint_queue.py"):
                continue  # the owning classes may touch their own attribute
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                # Attribute access only — `_watch_critical_worker_task(...)`
                # is a helper name, not a read of the private attribute.
                if re.search(r"\.\s*_worker_task\b", line):
                    offenders.append(f"{path.name}:{lineno}: {line.strip()}")

        assert not offenders, (
            "external readers of the private _worker_task attribute: " + "; ".join(offenders)
        )


class TestJobWorkerTaskReset:
    """#4577 SIBLING — JobWorker holds an equivalent _worker_task."""

    async def test_stop_clears_worker_task(self):
        engine = MagicMock()
        engine.jobs = {}
        engine.completed_job_ttl_hours = 1
        engine.cleanup_old_jobs = AsyncMock()
        jw = JobWorker(engine, max_concurrent_jobs=1, max_queue_size=4)

        jw._worker_task = asyncio.get_running_loop().create_task(asyncio.sleep(3600))
        await jw.stop()

        assert jw._worker_task is None


class TestCancelTaskThreadingContract:
    """#4575 — the docstring must describe the contract the code provides."""

    def test_cancel_task_does_not_claim_thread_safety(self):
        doc = inspect.getdoc(JobWorker.cancel_task) or ""
        assert "thread-safe" not in doc.lower().replace(" ", "-"), (
            "cancel_task calls Task.cancel() directly, which is loop-affine"
        )
        assert "event-loop thread" in doc, (
            "cancel_task must state which thread it may be called from"
        )

    def test_no_unbacked_thread_safety_claims_in_worker_modules(self):
        """CONSISTENCY: a thread-safety claim needs a lock or call_soon_threadsafe."""
        backend = Path(__file__).parent.parent.parent / "auralis-web" / "backend" / "core"
        for module in ("job_worker.py", "processing_engine.py"):
            source = (backend / module).read_text()
            tree = compile(source, module, "exec", flags=__import__("ast").PyCF_ONLY_AST)
            import ast

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                doc = ast.get_docstring(node) or ""
                if not re.search(r"thread[- ]?safe", doc, re.IGNORECASE):
                    continue
                body = ast.unparse(node)
                assert (
                    "lock" in body.lower() or "call_soon_threadsafe" in body
                ), (
                    f"{module}:{node.lineno} {node.name}() claims thread-safety "
                    f"without a lock or call_soon_threadsafe"
                )


# ============================================================================
# JobWorker.stop() drains in-flight jobs (#4543)
# ============================================================================
#
# stop() cancelled every in-flight job task but never awaited them, so it
# returned — logging "worker stopped" — while cancelled jobs were still
# unwinding. A job parked in asyncio.to_thread(processor.process, ...) kept a
# worker thread and a HybridProcessor alive past the point the lifespan tore
# down the library manager. Separately, _run_job's finally ended with an await
# (cleanup_old_jobs), which re-raises CancelledError immediately on the cancel
# path, so the TTL sweep never ran for any cancelled job.


def _engine_stub():
    engine = MagicMock()
    engine.jobs = {}
    engine.completed_job_ttl_hours = 1
    engine.cleanup_old_jobs = AsyncMock(return_value=0)
    return engine


class _Job:
    def __init__(self, job_id="j1"):
        self.job_id = job_id
        self.status = None
        self.completed_at = None


class TestStopDrainsInFlightJobs:
    async def test_stop_waits_for_cancelled_job_tasks(self):
        """Every task in _tasks must be done() by the time stop() returns."""
        engine = _engine_stub()
        started = asyncio.Event()
        unwound = asyncio.Event()

        async def process_job(job):
            started.set()
            try:
                await asyncio.Event().wait()  # blocks until cancelled
            except asyncio.CancelledError:
                # Simulate a job that takes a moment to unwind.
                await asyncio.sleep(0)
                unwound.set()
                raise

        engine.process_job = process_job
        jw = JobWorker(engine, max_concurrent_jobs=2, max_queue_size=4)

        job = _Job()
        task = asyncio.get_running_loop().create_task(jw._run_job(job))
        await asyncio.wait_for(started.wait(), timeout=2.0)

        await jw.stop()

        assert task.done(), (
            "stop() returned while a cancelled job task was still unwinding (#4543)"
        )
        assert unwound.is_set(), "the job's cancellation handler never completed"

    async def test_cleanup_runs_for_a_cancelled_job(self):
        """The TTL sweep must not be skipped on the cancel path."""
        engine = _engine_stub()
        started = asyncio.Event()

        async def process_job(job):
            started.set()
            await asyncio.Event().wait()

        engine.process_job = process_job
        jw = JobWorker(engine, max_concurrent_jobs=2, max_queue_size=4)

        job = _Job()
        asyncio.get_running_loop().create_task(jw._run_job(job))
        await asyncio.wait_for(started.wait(), timeout=2.0)

        await jw.stop()

        assert engine.cleanup_old_jobs.await_count >= 1, (
            "cleanup_old_jobs never ran for a job cancelled by stop() (#4543)"
        )

    async def test_semaphore_and_counter_restored_after_stop(self):
        """active_job_count back to 0 and every slot released."""
        engine = _engine_stub()
        started = asyncio.Event()

        async def process_job(job):
            started.set()
            await asyncio.Event().wait()

        engine.process_job = process_job
        jw = JobWorker(engine, max_concurrent_jobs=3, max_queue_size=4)

        job = _Job()
        asyncio.get_running_loop().create_task(jw._run_job(job))
        await asyncio.wait_for(started.wait(), timeout=2.0)
        assert jw.active_job_count == 1

        await jw.stop()

        assert jw.active_job_count == 0
        # All three slots free again.
        for _ in range(3):
            await asyncio.wait_for(jw._concurrency_semaphore.acquire(), timeout=1.0)

    async def test_stop_proceeds_when_a_task_refuses_to_unwind(self):
        """A task that swallows cancellation must not hang shutdown forever."""
        engine = _engine_stub()
        started = asyncio.Event()

        # Swallows the first cancellation (so it is still pending when the
        # drain times out) but yields to the second, so the test can never
        # leave a truly un-killable task behind for the loop teardown.
        async def process_job(job):
            started.set()
            swallowed = 0
            while True:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    swallowed += 1
                    if swallowed >= 2:
                        raise

        engine.process_job = process_job
        jw = JobWorker(engine, max_concurrent_jobs=1, max_queue_size=4)
        jw.STOP_DRAIN_TIMEOUT_SECONDS = 0.1  # keep the test fast

        job = _Job()
        task = asyncio.get_running_loop().create_task(jw._run_job(job))
        await asyncio.wait_for(started.wait(), timeout=2.0)

        # Must return despite the task not having unwound yet — asyncio.wait
        # leaves it pending rather than awaiting its cancellation.
        await asyncio.wait_for(jw.stop(), timeout=3.0)
        assert not task.done(), "the straggler should still be pending after stop()"

        # Clean up so the loop does not tear down with a live task.
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_stop_with_no_in_flight_jobs_is_a_noop(self):
        engine = _engine_stub()
        jw = JobWorker(engine, max_concurrent_jobs=1, max_queue_size=4)

        await asyncio.wait_for(jw.stop(), timeout=2.0)
        assert jw._worker_task is None
