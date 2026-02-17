"""
Test: process_job() does not block the event loop (fixes #2319)

Verifies that:
- load_audio(), processor.process(), and save() are all wrapped in asyncio.to_thread()
- The event loop remains responsive (concurrent tasks make progress) during processing
- Progress callbacks fire correctly throughout the job lifecycle
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from processing_engine import ProcessingEngine, ProcessingJob, ProcessingStatus


def _make_engine() -> ProcessingEngine:
    engine = ProcessingEngine.__new__(ProcessingEngine)
    engine.job_queue = asyncio.Queue()
    engine.active_jobs = 0
    engine.max_concurrent_jobs = 2
    engine.jobs = {}                  # dict[job_id, ProcessingJob]
    engine.progress_callbacks = {}    # dict[job_id, Callable]
    engine._processor_cache = {}
    engine._processor_cache_lock = asyncio.Lock()
    return engine


def _make_job(mode: str = "adaptive", reference_path: str | None = None) -> ProcessingJob:
    job = ProcessingJob.__new__(ProcessingJob)
    job.job_id = "test-job-001"
    job.input_path = "/fake/input.flac"
    job.output_path = "/fake/output.wav"
    job.mode = mode
    job.settings = {"output_format": "wav", "bit_depth": 16}
    if reference_path:
        job.settings["reference_path"] = reference_path
    job.status = ProcessingStatus.QUEUED
    job.started_at = None
    job.completed_at = None
    job.result_data = None
    job.error_message = None
    return job


@pytest.mark.asyncio
async def test_load_audio_offloaded_to_thread():
    """load_audio() must be called via asyncio.to_thread(), not directly."""
    engine = _make_engine()
    job = _make_job()

    fake_audio = np.zeros(44100, dtype=np.float32)
    fake_result = MagicMock()
    fake_result.audio = fake_audio

    thread_funcs: list[object] = []
    real_to_thread = asyncio.to_thread

    async def spy_to_thread(func, *args, **kwargs):
        thread_funcs.append(func)
        return await real_to_thread(func, *args, **kwargs)

    with (
        patch("processing_engine.load_audio", return_value=(fake_audio, 44100)) as mock_load,
        patch("processing_engine.save"),
        patch.object(engine, "_create_processor_config", return_value=MagicMock()),
        patch.object(engine, "_get_or_create_processor", return_value=MagicMock(
            process=MagicMock(return_value=fake_result)
        )),
        patch("asyncio.to_thread", side_effect=spy_to_thread),
    ):
        await engine.process_job(job)

    assert mock_load in thread_funcs, (
        "load_audio() must be called via asyncio.to_thread() (fixes #2319)"
    )


@pytest.mark.asyncio
async def test_processor_process_offloaded_to_thread():
    """processor.process() must be called via asyncio.to_thread()."""
    engine = _make_engine()
    job = _make_job()

    fake_audio = np.zeros(44100, dtype=np.float32)
    fake_result = MagicMock()
    fake_result.audio = fake_audio

    mock_processor = MagicMock()
    mock_processor.process = MagicMock(return_value=fake_result)

    thread_calls: list[object] = []
    real_to_thread = asyncio.to_thread

    async def spy_to_thread(func, *args, **kwargs):
        thread_calls.append(func)
        return await real_to_thread(func, *args, **kwargs)

    with (
        patch("processing_engine.load_audio", return_value=(fake_audio, 44100)),
        patch("processing_engine.save"),
        patch.object(engine, "_create_processor_config", return_value=MagicMock()),
        patch.object(engine, "_get_or_create_processor", return_value=mock_processor),
        patch("asyncio.to_thread", side_effect=spy_to_thread),
    ):
        await engine.process_job(job)

    assert mock_processor.process in thread_calls, (
        "processor.process() must be called via asyncio.to_thread() (fixes #2319)"
    )


@pytest.mark.asyncio
async def test_save_offloaded_to_thread():
    """save() must be called via asyncio.to_thread()."""
    engine = _make_engine()
    job = _make_job()

    fake_audio = np.zeros(44100, dtype=np.float32)
    fake_result = MagicMock()
    fake_result.audio = fake_audio

    thread_funcs: list[object] = []
    real_to_thread = asyncio.to_thread

    async def spy_to_thread(func, *args, **kwargs):
        thread_funcs.append(func)
        return await real_to_thread(func, *args, **kwargs)

    with (
        patch("processing_engine.load_audio", return_value=(fake_audio, 44100)),
        patch("processing_engine.save") as mock_save,
        patch.object(engine, "_create_processor_config", return_value=MagicMock()),
        patch.object(engine, "_get_or_create_processor", return_value=MagicMock(
            process=MagicMock(return_value=fake_result)
        )),
        patch("asyncio.to_thread", side_effect=spy_to_thread),
    ):
        await engine.process_job(job)

    assert mock_save in thread_funcs, (
        "save() must be called via asyncio.to_thread() (fixes #2319)"
    )


@pytest.mark.asyncio
async def test_event_loop_responsive_during_processing():
    """
    Concurrent tasks must make progress while process_job() is running.

    This is the core regression test for #2319: if blocking calls were
    not offloaded, the concurrent counter task would not advance at all.
    """
    engine = _make_engine()
    job = _make_job()

    fake_audio = np.zeros(44100, dtype=np.float32)
    fake_result = MagicMock()
    fake_result.audio = fake_audio

    counter: list[int] = [0]

    async def concurrent_task():
        """Increment a counter 10 times while process_job() runs."""
        for _ in range(10):
            await asyncio.sleep(0)
            counter[0] += 1

    def slow_load(path):
        import time
        time.sleep(0.05)  # 50 ms blocking — simulates disk I/O
        return (fake_audio, 44100)

    def slow_process(*args):
        import time
        time.sleep(0.05)  # 50 ms blocking — simulates CPU work
        return fake_result

    with (
        patch("processing_engine.load_audio", side_effect=slow_load),
        patch("processing_engine.save"),
        patch.object(engine, "_create_processor_config", return_value=MagicMock()),
        patch.object(engine, "_get_or_create_processor", return_value=MagicMock(
            process=MagicMock(side_effect=slow_process)
        )),
    ):
        await asyncio.gather(
            engine.process_job(job),
            concurrent_task(),
        )

    assert counter[0] == 10, (
        f"Concurrent task only advanced {counter[0]}/10 iterations — "
        "event loop was blocked during process_job() (bug #2319 still present)"
    )
    assert job.status == ProcessingStatus.COMPLETED


@pytest.mark.asyncio
async def test_progress_callbacks_fire_correctly():
    """Progress callbacks must fire at 0%, 20%, 40%, 80%, and 100%."""
    engine = _make_engine()
    job = _make_job()

    fake_audio = np.zeros(44100, dtype=np.float32)
    fake_result = MagicMock()
    fake_result.audio = fake_audio

    progress_log: list[float] = []

    async def capture_progress(job_id: str, pct: float, msg: str):
        progress_log.append(pct)

    engine.jobs[job.job_id] = job
    engine.progress_callbacks[job.job_id] = capture_progress

    with (
        patch("processing_engine.load_audio", return_value=(fake_audio, 44100)),
        patch("processing_engine.save"),
        patch.object(engine, "_create_processor_config", return_value=MagicMock()),
        patch.object(engine, "_get_or_create_processor", return_value=MagicMock(
            process=MagicMock(return_value=fake_result)
        )),
    ):
        await engine.process_job(job)

    assert 0.0 in progress_log, "0% progress callback missing"
    assert 20.0 in progress_log, "20% progress callback missing"
    assert 40.0 in progress_log, "40% progress callback missing"
    assert 80.0 in progress_log, "80% progress callback missing"
    assert 100.0 in progress_log, "100% progress callback missing"


@pytest.mark.asyncio
async def test_reference_load_also_offloaded():
    """Reference audio load must also be offloaded to a thread (reference mode)."""
    engine = _make_engine()
    job = _make_job(mode="reference", reference_path="/fake/reference.flac")

    fake_audio = np.zeros(44100, dtype=np.float32)
    fake_result = MagicMock()
    fake_result.audio = fake_audio

    thread_funcs: list[object] = []
    real_to_thread = asyncio.to_thread

    async def spy_to_thread(func, *args, **kwargs):
        thread_funcs.append(func)
        return await real_to_thread(func, *args, **kwargs)

    with (
        patch("processing_engine.load_audio", return_value=(fake_audio, 44100)) as mock_load,
        patch("processing_engine.save"),
        patch("pathlib.Path.exists", return_value=True),
        patch.object(engine, "_create_processor_config", return_value=MagicMock()),
        patch.object(engine, "_get_or_create_processor", return_value=MagicMock(
            process=MagicMock(return_value=fake_result)
        )),
        patch("asyncio.to_thread", side_effect=spy_to_thread),
    ):
        await engine.process_job(job)

    # Both input and reference loads must go through to_thread
    load_via_thread = thread_funcs.count(mock_load)
    assert load_via_thread >= 2, (
        f"Expected both input and reference load_audio() calls via to_thread, "
        f"got {load_via_thread} (fixes #2319)"
    )
