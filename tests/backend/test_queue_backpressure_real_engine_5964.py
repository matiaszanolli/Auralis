"""
Processing-queue backpressure against a RUNNING engine (#5964)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The older #2332 tests inject ``asyncio.QueueFull`` into a mock engine, or fill a queue nothing
drains, so they stayed green while the worker drained the bounded queue into semaphore-parked tasks
and ``QueueFull`` / the 503 could never fire (#5949), and while ``stop()`` let a parked job start
(#5950). These start a real ``ProcessingEngine`` + ``JobWorker`` with one slot and a ``process_job``
that blocks, and assert the contract end to end: the queue holds the backlog, the next submit is
rejected, the HTTP route answers 503, and ``stop()`` never starts a job that was only queued.
"""

import asyncio
import contextlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.job_models import ProcessingStatus
from core.processing_engine import ProcessingEngine
from routers.processing_api import create_processing_router

pytestmark = pytest.mark.asyncio


class _Gate:
    """A process_job stand-in that records who started and blocks until released."""

    def __init__(self) -> None:
        self.started: list[str] = []
        self.release = asyncio.Event()

    async def __call__(self, job) -> None:
        self.started.append(job.job_id)
        await self.release.wait()


async def _until(predicate, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition never became true")
        await asyncio.sleep(0.01)


@contextlib.asynccontextmanager
async def _running_engine(gate: _Gate, **kwargs):
    engine = ProcessingEngine(max_concurrent_jobs=1, **kwargs)
    with patch.object(engine, "process_job", gate):
        worker = asyncio.create_task(engine.start_worker())
        try:
            yield engine
        finally:
            gate.release.set()
            await engine.stop_worker()
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await worker


async def _submit(engine: ProcessingEngine, name: str):
    job = await engine.create_job(input_path=f"/{name}.wav", settings={})
    await engine.submit_job(job)
    return job


async def test_a_full_queue_rejects_the_next_submit_while_the_worker_is_running():
    gate = _Gate()
    async with _running_engine(gate, max_queue_size=1) as engine:
        running = await _submit(engine, "running")
        await _until(lambda: gate.started == [running.job_id])  # the one slot is busy
        queued = await _submit(engine, "queued")  # the queue (size 1) holds the backlog
        await asyncio.sleep(0.05)  # let a dispatcher that dequeues eagerly do so
        rejected = await engine.create_job(input_path="/rejected.wav", settings={})

        with pytest.raises(asyncio.QueueFull):
            await engine.submit_job(rejected)

        assert gate.started == [running.job_id], "the queued job must wait for a slot, not park on one"
        assert queued.job_id in engine.jobs and rejected.job_id not in engine.jobs


async def test_a_slot_freeing_up_makes_room_again():
    gate = _Gate()
    async with _running_engine(gate, max_queue_size=1) as engine:
        first = await _submit(engine, "first")
        await _until(lambda: gate.started == [first.job_id])
        second = await _submit(engine, "second")
        await asyncio.sleep(0.05)
        with pytest.raises(asyncio.QueueFull):
            await engine.submit_job(await engine.create_job(input_path="/x.wav", settings={}))

        gate.release.set()  # first finishes -> second is dispatched -> the queue drains
        await _until(lambda: second.job_id in gate.started)

        await _submit(engine, "third")  # no QueueFull now


async def test_stop_never_starts_a_job_that_was_only_queued():
    gate = _Gate()
    engine = ProcessingEngine(max_concurrent_jobs=1, max_queue_size=5)
    with patch.object(engine, "process_job", gate):
        worker = asyncio.create_task(engine.start_worker())
        running = await _submit(engine, "running")
        await _until(lambda: gate.started == [running.job_id])
        waiting = [await _submit(engine, f"waiting{i}") for i in range(3)]

        await engine.stop_worker()  # unwinds the running job, frees its slot
        gate.release.set()
        await asyncio.sleep(0.1)  # a still-live dispatcher would have taken the freed slot by now
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await worker

    assert gate.started == [running.job_id], f"a queued job started during shutdown: {gate.started}"
    assert {engine.jobs[j.job_id].status for j in waiting} == {ProcessingStatus.INTERRUPTED}


async def test_the_http_route_answers_503_from_a_real_full_queue(tmp_path):
    gate = _Gate()
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 40)

    async with _running_engine(gate, max_queue_size=1) as engine:
        app = FastAPI()
        app.include_router(create_processing_router(lambda: engine))
        running = await _submit(engine, "running")
        await _until(lambda: gate.started == [running.job_id])
        await _submit(engine, "queued")
        await asyncio.sleep(0.05)

        def post():
            with patch("routers.processing_api.validate_file_path", return_value=audio):
                return TestClient(app).post(
                    "/api/processing/process",
                    json={"input_path": str(audio), "settings": {"mode": "adaptive"}},
                )

        response = await asyncio.to_thread(post)

    assert response.status_code == 503
    assert "queue" in response.json()["detail"].lower()


async def test_the_upload_route_answers_503_from_a_real_full_queue():
    import io
    import json

    gate = _Gate()
    async with _running_engine(gate, max_queue_size=1) as engine:
        app = FastAPI()
        app.include_router(create_processing_router(lambda: engine))
        running = await _submit(engine, "running")
        await _until(lambda: gate.started == [running.job_id])
        await _submit(engine, "queued")
        await asyncio.sleep(0.05)

        def post():
            return TestClient(app).post(
                "/api/processing/upload-and-process",
                files={"file": ("test.wav", io.BytesIO(b"RIFF" + b"\x00" * 40), "audio/wav")},
                data={"settings": json.dumps({"mode": "adaptive"})},
            )

        response = await asyncio.to_thread(post)

    assert response.status_code == 503
    assert "queue" in response.json()["detail"].lower()
