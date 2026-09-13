"""A timed-out DSP call must not pin I/O-pool workers or leak a poisoned processor (#5335).

``asyncio.wait_for`` cancels only the asyncio wrapper; the OS thread running the
hung DSP keeps going. Mastering-job DSP ran on the default (DB-sized, 8-worker)
I/O pool via ``asyncio.to_thread``, so each job timeout pinned one of the
workers every repository call shares. And the per-chunk ``TimeoutError``
branch never dropped the pooled HybridProcessor that abandoned thread may
still be advancing, so the next stream of the track reused it.
"""

import asyncio
import inspect
import threading
from unittest.mock import AsyncMock, Mock

import pytest

# tests/backend/conftest.py puts auralis-web/backend on sys.path.
import core.audio_stream_controller as asc
from core import executors, job_execution
from core.audio_stream_controller import AudioStreamController


@pytest.fixture(autouse=True)
async def _clean_executors():
    """The pools are module-global and replace the loop's default executor."""
    executors.shutdown_executors()
    try:
        yield
    finally:
        executors.shutdown_executors()


class TestJobPool:
    @pytest.mark.asyncio
    async def test_job_pool_is_its_own_bounded_pool(self):
        executors.install_executors()
        job_pool = executors.get_job_executor()

        assert job_pool is not None
        assert job_pool is not executors.get_io_executor()
        assert job_pool is not executors.get_stream_executor()
        assert job_pool._max_workers == executors.JOB_POOL_SIZE

    @pytest.mark.asyncio
    async def test_run_in_job_executor_runs_on_the_job_pool(self):
        executors.install_executors()

        name = await executors.run_in_job_executor(lambda: threading.current_thread().name)

        assert name.startswith("auralis-job")

    @pytest.mark.asyncio
    async def test_run_in_job_executor_works_with_no_pool_installed(self):
        assert executors.get_job_executor() is None
        assert await executors.run_in_job_executor(pow, 2, 10) == 1024

    @pytest.mark.asyncio
    async def test_a_hung_job_leaves_every_io_worker_available(self):
        executors.install_executors()
        release = threading.Event()
        try:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(
                    executors.run_in_job_executor(release.wait, 10), timeout=0.05
                )

            # All IO workers must be able to run at once. Had the abandoned job
            # thread taken one, only IO_POOL_SIZE - 1 could reach the barrier
            # and it would break on its timeout.
            barrier = threading.Barrier(executors.IO_POOL_SIZE, timeout=5)
            await asyncio.gather(
                *(asyncio.to_thread(barrier.wait) for _ in range(executors.IO_POOL_SIZE))
            )
        finally:
            release.set()

    @pytest.mark.asyncio
    async def test_shutdown_clears_the_job_pool(self):
        executors.install_executors()
        executors.shutdown_executors()
        assert executors.get_job_executor() is None

    def test_every_job_dsp_call_is_submitted_to_the_job_pool(self):
        """WIRING: all three processor.process sites in execute_job."""
        source = inspect.getsource(job_execution)
        assert "asyncio.to_thread(processor.process" not in source
        assert source.count("run_in_job_executor(processor.process") == 3


def _hung_processor(preset: str | None = "adaptive") -> Mock:
    processor = Mock()
    processor.track_id = 7
    processor.total_chunks = 5
    processor.sample_rate = 44100
    processor.channels = 2
    processor.preset = preset
    processor.intensity = 1.0
    processor.mastering_targets = {"target_lufs": -14.0}
    processor.processor_config = Mock(name="processor_config")

    async def _hang(*_a, **_k):
        await asyncio.sleep(10)

    processor.process_chunk_safe = AsyncMock(side_effect=_hang)
    return processor


def _connected_ws() -> Mock:
    ws = Mock()
    ws.client_state = Mock()
    ws.client_state.name = "CONNECTED"
    return ws


class TestChunkTimeoutInvalidatesTheProcessor:
    @pytest.mark.asyncio
    async def test_timed_out_chunk_drops_the_pooled_processor(self, monkeypatch):
        monkeypatch.setattr(asc, "CHUNK_PROCESS_TIMEOUT", 0.05)
        processor = _hung_processor()

        with pytest.raises(TimeoutError):
            await AudioStreamController()._process_chunk_only(0, processor, _connected_ws())

        processor._processor_factory.invalidate.assert_called_once_with(
            track_id=7,
            preset="adaptive",
            mastering_targets={"target_lufs": -14.0},
            config=processor.processor_config,
        )

    @pytest.mark.asyncio
    async def test_unprocessed_stream_has_no_pooled_processor_to_drop(self, monkeypatch):
        monkeypatch.setattr(asc, "CHUNK_PROCESS_TIMEOUT", 0.05)
        processor = _hung_processor(preset=None)

        with pytest.raises(TimeoutError):
            await AudioStreamController()._process_chunk_only(0, processor, _connected_ws())

        processor._processor_factory.invalidate.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_failing_invalidate_does_not_mask_the_timeout(self, monkeypatch):
        monkeypatch.setattr(asc, "CHUNK_PROCESS_TIMEOUT", 0.05)
        processor = _hung_processor()
        processor._processor_factory.invalidate.side_effect = RuntimeError("factory gone")

        with pytest.raises(TimeoutError, match="timed out"):
            await AudioStreamController()._process_chunk_only(0, processor, _connected_ws())
