"""
Tests for ProcessingEngine.cancel_job() actually stopping processing (issue #2217)

Verifies that:
- cancel_job() on a QUEUED job prevents it from starting at all
- cancel_job() on a PROCESSING job cancels the asyncio Task
- Task.cancel() is called when a running job is cancelled
- Status is CANCELLED (not FAILED) after cancellation
- Worker continues to process subsequent jobs after a cancellation
- Cancelling a job that's already complete/failed is a no-op
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.processing_engine import ProcessingEngine, ProcessingJob, ProcessingStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine() -> ProcessingEngine:
    engine = ProcessingEngine(max_concurrent_jobs=2)
    return engine


def _make_job(job_id: str = "job-1") -> ProcessingJob:
    job = ProcessingJob(
        job_id=job_id,
        input_path="/fake/input.wav",
        output_path="/fake/output.wav",
        settings={},
        mode="adaptive",
    )
    return job


# ---------------------------------------------------------------------------
# Tests: cancel_job() return value and status
# ---------------------------------------------------------------------------

def test_cancel_queued_job_returns_true():
    engine = _make_engine()
    job = _make_job()
    engine.jobs[job.job_id] = job
    assert engine.cancel_job(job.job_id) is True


def test_cancel_queued_job_sets_status_cancelled():
    engine = _make_engine()
    job = _make_job()
    engine.jobs[job.job_id] = job
    engine.cancel_job(job.job_id)
    assert job.status == ProcessingStatus.CANCELLED


def test_cancel_queued_job_sets_completed_at():
    engine = _make_engine()
    job = _make_job()
    engine.jobs[job.job_id] = job
    before = datetime.now()
    engine.cancel_job(job.job_id)
    assert job.completed_at is not None
    assert job.completed_at >= before


def test_cancel_nonexistent_job_returns_false():
    engine = _make_engine()
    assert engine.cancel_job("does-not-exist") is False


def test_cancel_completed_job_returns_false():
    engine = _make_engine()
    job = _make_job()
    job.status = ProcessingStatus.COMPLETED
    engine.jobs[job.job_id] = job
    assert engine.cancel_job(job.job_id) is False
    assert job.status == ProcessingStatus.COMPLETED  # unchanged


def test_cancel_failed_job_returns_false():
    engine = _make_engine()
    job = _make_job()
    job.status = ProcessingStatus.FAILED
    engine.jobs[job.job_id] = job
    assert engine.cancel_job(job.job_id) is False


# ---------------------------------------------------------------------------
# Tests: Task.cancel() is called for in-flight jobs
# ---------------------------------------------------------------------------

def test_cancel_processing_job_cancels_task():
    """cancel_job() must call task.cancel() for a PROCESSING job."""
    engine = _make_engine()
    job = _make_job()
    job.status = ProcessingStatus.PROCESSING
    engine.jobs[job.job_id] = job

    mock_task = MagicMock()
    mock_task.done.return_value = False
    engine._tasks[job.job_id] = mock_task

    engine.cancel_job(job.job_id)

    mock_task.cancel.assert_called_once()


def test_cancel_does_not_call_task_cancel_if_task_done():
    """If the task is already done, task.cancel() must NOT be called."""
    engine = _make_engine()
    job = _make_job()
    job.status = ProcessingStatus.PROCESSING
    engine.jobs[job.job_id] = job

    mock_task = MagicMock()
    mock_task.done.return_value = True
    engine._tasks[job.job_id] = mock_task

    engine.cancel_job(job.job_id)

    mock_task.cancel.assert_not_called()


def test_cancel_queued_job_no_task_cancel_needed():
    """QUEUED jobs have no task yet — cancel_job() must not raise."""
    engine = _make_engine()
    job = _make_job()
    engine.jobs[job.job_id] = job
    # No entry in _tasks — cancelling should not blow up
    engine.cancel_job(job.job_id)
    assert job.status == ProcessingStatus.CANCELLED


# ---------------------------------------------------------------------------
# Tests: process_job() honours pre-cancellation (QUEUED guard)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_job_skips_if_already_cancelled():
    """
    If cancel_job() fires before the worker calls process_job(), the job
    must be skipped without any processing.
    """
    engine = _make_engine()
    job = _make_job()
    engine.jobs[job.job_id] = job

    # Pre-cancel before processing starts
    engine.cancel_job(job.job_id)
    assert job.status == ProcessingStatus.CANCELLED

    # process_job() must return immediately without touching job.status
    await engine.process_job(job)

    assert job.status == ProcessingStatus.CANCELLED
    assert job.started_at is None  # never started


# ---------------------------------------------------------------------------
# Tests: CancelledError path in process_job()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_job_cancelled_error_sets_status():
    """
    When task.cancel() fires during processing, process_job() must set
    job.status = CANCELLED and re-raise CancelledError.

    We patch asyncio.to_thread to hang so we have a controlled window to
    call task.cancel() and verify the correct exception + status outcome.
    """
    engine = _make_engine()
    job = _make_job()
    engine.jobs[job.job_id] = job

    load_started = asyncio.Event()

    async def hanging_to_thread(func, *args, **kwargs):
        load_started.set()
        await asyncio.sleep(100)  # hang until cancelled

    with patch("core.processing_engine.asyncio.to_thread", side_effect=hanging_to_thread):
        task = asyncio.create_task(engine.process_job(job))
        await load_started.wait()  # ensure we're inside the first to_thread call
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert job.status == ProcessingStatus.CANCELLED
    assert job.completed_at is not None


# ---------------------------------------------------------------------------
# Tests: worker continues after cancellation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_continues_after_job_cancellation():
    """
    After a job is cancelled, start_worker() must process the next job
    normally — the worker loop must not be killed.
    """
    engine = _make_engine()

    completed_jobs: list[str] = []

    async def fake_process_job(job: ProcessingJob) -> None:
        if job.job_id == "job-cancel":
            raise asyncio.CancelledError()
        job.status = ProcessingStatus.COMPLETED
        completed_jobs.append(job.job_id)

    cancel_job = _make_job("job-cancel")
    cancel_job.status = ProcessingStatus.CANCELLED  # already marked
    engine.jobs[cancel_job.job_id] = cancel_job

    normal_job = _make_job("job-normal")
    engine.jobs[normal_job.job_id] = normal_job

    await engine.job_queue.put(cancel_job)
    await engine.job_queue.put(normal_job)

    with patch.object(engine, "process_job", side_effect=fake_process_job):
        worker_task = asyncio.create_task(engine.start_worker())

        # Give the worker time to process both jobs
        await asyncio.sleep(0.1)
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    assert "job-normal" in completed_jobs, (
        "Worker must continue processing after a job cancellation"
    )
