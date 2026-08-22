"""
Tests for ProcessingEngine (Fixed API Signatures)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the job queue system with correct API signatures.
"""

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.processing_engine import (
    ProcessingEngine,
    ProcessingJob,
    ProcessingStatus,
    _safe_error_message,
)


@pytest.fixture
def temp_audio_file():
    """Create a temporary audio file for testing"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        # Write minimal WAV header
        f.write(b'RIFF')
        f.write((36).to_bytes(4, 'little'))
        f.write(b'WAVE')
        f.write(b'fmt ')
        f.write((16).to_bytes(4, 'little'))
        f.write((1).to_bytes(2, 'little'))
        f.write((1).to_bytes(2, 'little'))
        f.write((44100).to_bytes(4, 'little'))
        f.write((88200).to_bytes(4, 'little'))
        f.write((2).to_bytes(2, 'little'))
        f.write((16).to_bytes(2, 'little'))
        f.write(b'data')
        f.write((0).to_bytes(4, 'little'))
        path = Path(f.name)

    yield path

    if path.exists():
        path.unlink()


@pytest.fixture
def engine():
    """Create a processing engine instance"""
    return ProcessingEngine(max_concurrent_jobs=2)


class TestProcessingEngine:
    """Test ProcessingEngine with correct API"""

    def test_engine_initialization(self, engine):
        """Test engine initializes correctly"""
        assert engine.max_concurrent_jobs == 2
        assert len(engine.jobs) == 0
        assert isinstance(engine.job_queue, asyncio.Queue)

    @pytest.mark.asyncio
    async def test_create_job(self, engine, temp_audio_file):
        """Test creating a job"""
        job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )

        assert job.job_id is not None
        assert job.input_path == str(temp_audio_file)
        assert job.status == ProcessingStatus.QUEUED
        assert job.job_id in engine.jobs

    @pytest.mark.asyncio
    async def test_submit_job(self, engine, temp_audio_file):
        """Test submitting a job to queue"""
        job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )

        job_id = await engine.submit_job(job)

        assert job_id == job.job_id
        assert engine.job_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_get_job(self, engine, temp_audio_file):
        """Test retrieving a job"""
        job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )

        retrieved = await engine.get_job(job.job_id)

        assert retrieved is not None
        assert retrieved.job_id == job.job_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, engine):
        """Test getting nonexistent job returns None"""
        job = await engine.get_job("nonexistent-id")
        assert job is None

    @pytest.mark.asyncio
    async def test_cancel_job(self, engine, temp_audio_file):
        """Test cancelling a job"""
        job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )

        result = await engine.cancel_job(job.job_id)

        assert result is True
        assert job.status == ProcessingStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, engine):
        """Test cancelling nonexistent job"""
        result = await engine.cancel_job("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_all_jobs(self, engine, temp_audio_file):
        """Test getting all jobs"""
        job1 = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )
        job2 = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "gentle"}
        )

        all_jobs = engine.get_all_jobs()

        assert len(all_jobs) == 2
        assert job1 in all_jobs
        assert job2 in all_jobs

    def test_get_queue_status(self, engine, temp_audio_file):
        """Test queue status"""
        status = engine.get_queue_status()

        assert "total_jobs" in status
        assert "queued" in status
        assert "processing" in status
        assert "completed" in status
        assert "failed" in status
        assert "max_concurrent" in status
        assert status["max_concurrent"] == 2

    @pytest.mark.asyncio
    async def test_queue_status_with_jobs(self, engine, temp_audio_file):
        """Test queue status with jobs"""
        job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )
        await engine.submit_job(job)

        status = engine.get_queue_status()

        assert status["total_jobs"] >= 1
        assert status["queued"] >= 1

    @pytest.mark.asyncio
    async def test_register_progress_callback(self, engine):
        """Test registering progress callback"""
        callback_called = {"called": False}

        async def test_callback(job_id, progress, message):
            callback_called["called"] = True

        await engine.register_progress_callback("test-job", test_callback)

        assert "test-job" in engine.progress_callbacks

    @pytest.mark.asyncio
    async def test_cleanup_old_jobs(self, engine, temp_audio_file):
        """Test cleaning up old jobs"""
        from datetime import datetime, timedelta

        job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )
        job.status = ProcessingStatus.COMPLETED
        job.completed_at = datetime.now() - timedelta(hours=25)  # Old job

        # Add job to engine's jobs dict
        engine.jobs[job.job_id] = job

        removed = await engine.cleanup_old_jobs(max_age_hours=24)

        assert removed == 1
        assert job.job_id not in engine.jobs

    @pytest.mark.asyncio
    async def test_cleanup_old_jobs_file_deletion_offloaded_via_to_thread(
        self, engine, temp_audio_file
    ):
        """#4754: the per-job filesystem check/delete loop (Phase 2, outside
        _jobs_lock per #3327) is unbounded — grows with job count — and used
        to run directly on the event loop."""
        from datetime import datetime, timedelta

        job = await engine.create_job(
            input_path=str(temp_audio_file), settings={"mode": "adaptive"}
        )
        job.status = ProcessingStatus.COMPLETED
        job.completed_at = datetime.now() - timedelta(hours=25)
        engine.jobs[job.job_id] = job

        with patch(
            "core.processing_engine.asyncio.to_thread", wraps=asyncio.to_thread
        ) as mock_to_thread:
            removed = await engine.cleanup_old_jobs(max_age_hours=24)

        assert removed == 1
        assert mock_to_thread.called, (
            "cleanup_old_jobs's filesystem check/delete phase must be "
            "offloaded via asyncio.to_thread, not run directly on the "
            "event loop (#4754)"
        )

    @pytest.mark.asyncio
    async def test_multiple_jobs(self, engine, temp_audio_file):
        """Test submitting multiple jobs"""
        jobs = []
        for i in range(3):
            job = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive"}
            )
            await engine.submit_job(job)
            jobs.append(job)

        assert len(engine.jobs) == 3
        assert engine.job_queue.qsize() == 3

        status = engine.get_queue_status()
        assert status["total_jobs"] == 3


class TestProcessingJobProcessing:
    """Test job processing with mocks"""

    @pytest.mark.asyncio
    async def test_process_job_with_mocks(self, temp_audio_file):
        """Test processing with mocked dependencies (fixes #3818).

        This test used to mock process()'s return value as a bare Mock()
        with .audio/.lufs attributes — a shape production stopped accepting
        after #3489 (HybridProcessor.process() returns a bare np.ndarray; the
        old result-object contract silently raised AttributeError on every
        successful job). The test's own `except Exception: pass` absorbed the
        resulting TypeError and passed without exercising a single line of
        the post-process save/telemetry/completion flow — exactly the
        bug-masking pattern that let #3489 ship. No more try/except: a
        regression here must fail the test.

        #4757: this test also used to mock the telemetry side-channel with a
        shape that never occurs in production — get_processing_info() never
        returns "last_processing_time"/"last_lufs" keys (it's a fixed 7-key
        static-config dict), and last_content_profile is always a dict, never
        an object with a `.genre` attribute — so the test validated the exact
        bug it should have caught. Mocks now match HybridProcessor's real
        shape: last_content_profile as the legacy AdaptiveMode dict
        (genre_info.primary), continuous_mode.last_fingerprint for LUFS.
        """
        engine = ProcessingEngine(max_concurrent_jobs=1)

        with patch('core.job_execution.load_audio') as mock_load, \
             patch('core.processing_engine.HybridProcessor') as mock_processor, \
             patch('core.job_execution.save') as mock_save:

            # Setup mocks
            mock_load.return_value = (np.zeros((1000, 2), dtype=np.float32), 44100)

            mock_proc_instance = Mock()
            # HybridProcessor.process() returns a bare np.ndarray — the
            # post-#3489 contract asserted by processing_engine.py's
            # isinstance(result, np.ndarray) guard.
            mock_proc_instance.process.return_value = np.zeros((1000, 2), dtype=np.float32)
            # Telemetry side-channels _finalize_job actually reads (#4757):
            # last_content_profile is a dict (legacy AdaptiveMode shape here,
            # genre lives under genre_info.primary); continuous_mode's
            # last_fingerprint carries the real measured LUFS on the
            # production (continuous-space) path and takes precedence when
            # present — set to None here so the legacy dict's estimated_lufs
            # is exercised instead.
            mock_proc_instance.last_content_profile = {
                "genre_info": {"primary": "rock"},
                "estimated_lufs": -14.0,
            }
            mock_proc_instance.continuous_mode.last_fingerprint = None
            mock_processor.return_value = mock_proc_instance

            # Create and process job
            job = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={
                    "mode": "adaptive",
                    "output_format": "wav",
                    "bit_depth": 16
                }
            )

            await engine.process_job(job)

            assert job.status == ProcessingStatus.COMPLETED
            assert job.result_data is not None
            # Real wall-clock duration (job.started_at → completion), not a
            # mocked value — just assert it was actually measured.
            assert isinstance(job.result_data["processing_time"], float)
            assert job.result_data["processing_time"] >= 0.0
            assert job.result_data["lufs"] == -14.0
            assert job.result_data["genre_detected"] == "rock"

            mock_save.assert_called_once()
            assert mock_save.call_args.kwargs["subtype"] == "PCM_16"

    @pytest.mark.asyncio
    async def test_process_job_lufs_from_continuous_mode_fingerprint(self, temp_audio_file):
        """The default/production path (use_continuous_space=True, #4757).

        ContinuousMode is "the default and the only value the app ever
        sets" (hybrid_processor.py's own docstring) — it never runs genre
        classification, but its 25D fingerprint carries a real measured
        LUFS. That fingerprint value must win over any legacy
        last_content_profile estimate, and genre_detected must stay honestly
        None rather than fabricating a value.
        """
        engine = ProcessingEngine(max_concurrent_jobs=1)

        with patch('core.job_execution.load_audio') as mock_load, \
             patch('core.processing_engine.HybridProcessor') as mock_processor, \
             patch('core.job_execution.save') as mock_save:

            mock_load.return_value = (np.zeros((1000, 2), dtype=np.float32), 44100)

            mock_proc_instance = Mock()
            mock_proc_instance.process.return_value = np.zeros((1000, 2), dtype=np.float32)
            # Continuous-mode shape: no genre_info anywhere.
            mock_proc_instance.last_content_profile = {
                "fingerprint": {"lufs": -9.5},
                "coordinates": Mock(),
                "parameters": Mock(),
            }
            mock_proc_instance.continuous_mode.last_fingerprint = {"lufs": -9.5}
            mock_processor.return_value = mock_proc_instance

            job = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive", "output_format": "wav", "bit_depth": 16},
            )
            await engine.process_job(job)

            assert job.status == ProcessingStatus.COMPLETED
            assert job.result_data is not None
            assert job.result_data["lufs"] == -9.5
            assert job.result_data["genre_detected"] is None
            mock_save.assert_called_once()


class TestJobCreation:
    """Test job creation with different modes"""

    @pytest.mark.asyncio
    async def test_create_adaptive_job(self, engine, temp_audio_file):
        """Test creating adaptive mode job"""
        job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
            mode="adaptive"
        )

        assert job.mode == "adaptive"
        assert job.status == ProcessingStatus.QUEUED

    @pytest.mark.asyncio
    async def test_create_reference_job(self, engine, temp_audio_file):
        """Test creating reference mode job"""
        job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "reference"},
            mode="reference"
        )

        assert job.mode == "reference"

    @pytest.mark.asyncio
    async def test_create_hybrid_job(self, engine, temp_audio_file):
        """Test creating hybrid mode job"""
        job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "hybrid"},
            mode="hybrid",
            reference_path="/path/to/reference.wav"
        )

        assert job.mode == "hybrid"
        assert "reference_path" in job.settings


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_create_job_with_invalid_file(self, engine):
        """Test creating job with nonexistent file"""
        job = await engine.create_job(
            input_path="/nonexistent/file.wav",
            settings={"mode": "adaptive"}
        )

        # Job should be created (will fail during processing)
        assert job.job_id is not None
        assert job.input_path == "/nonexistent/file.wav"

    @pytest.mark.asyncio
    async def test_concurrent_limit(self, engine, temp_audio_file):
        """Test concurrent job limit"""
        for i in range(5):
            job = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive"}
            )
            await engine.submit_job(job)

        status = engine.get_queue_status()
        assert status["max_concurrent"] == 2
        assert status["total_jobs"] == 5

    def test_empty_queue(self, engine):
        """Test operations on empty queue"""
        all_jobs = engine.get_all_jobs()
        assert len(all_jobs) == 0

        status = engine.get_queue_status()
        assert status["total_jobs"] == 0


class TestQueueBackpressure:
    """Tests for bounded queue and semaphore-based concurrency (issue #2332)"""

    def test_max_queue_size_default(self):
        """Default max_queue_size is 20"""
        engine = ProcessingEngine()
        assert engine.max_queue_size == 20
        assert engine.job_queue.maxsize == 20

    def test_max_queue_size_configurable(self):
        """max_queue_size constructor parameter is stored and applied"""
        engine = ProcessingEngine(max_queue_size=5)
        assert engine.max_queue_size == 5
        assert engine.job_queue.maxsize == 5

    @pytest.mark.asyncio
    async def test_submit_job_raises_queue_full_when_at_capacity(self, temp_audio_file):
        """submit_job raises asyncio.QueueFull when maxsize is exceeded"""
        engine = ProcessingEngine(max_queue_size=3)

        # Fill the queue to capacity
        for _ in range(3):
            job = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive"},
            )
            await engine.submit_job(job)

        assert engine.job_queue.full()

        # One more submit must raise QueueFull
        overflow_job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
        )
        with pytest.raises(asyncio.QueueFull):
            await engine.submit_job(overflow_job)

    @pytest.mark.asyncio
    async def test_queue_full_removes_job_from_jobs_dict(self, temp_audio_file):
        """When submit_job raises QueueFull the job is cleaned from self.jobs"""
        engine = ProcessingEngine(max_queue_size=1)

        first_job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
        )
        await engine.submit_job(first_job)

        overflow_job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
        )
        with pytest.raises(asyncio.QueueFull):
            await engine.submit_job(overflow_job)

        # Overflow job must not remain in the dict
        assert overflow_job.job_id not in engine.jobs

    def test_get_queue_status_exposes_max_queue_size_and_full_flag(self, engine):
        """get_queue_status includes max_queue_size and queue_full fields"""
        status = engine.get_queue_status()
        assert "max_queue_size" in status
        assert "queue_full" in status
        assert status["max_queue_size"] == engine.max_queue_size
        assert status["queue_full"] is False

    @pytest.mark.asyncio
    async def test_processing_count_reflects_semaphore_value(self):
        """get_queue_status()['processing'] tracks active jobs via _active_job_count (#2459)"""
        engine = ProcessingEngine(max_concurrent_jobs=3)

        assert engine.get_queue_status()["processing"] == 0

        # Simulate two jobs holding concurrency slots (mimic start_worker behavior)
        await engine._concurrency_semaphore.acquire()
        engine._active_job_count += 1
        assert engine.get_queue_status()["processing"] == 1

        await engine._concurrency_semaphore.acquire()
        engine._active_job_count += 1
        assert engine.get_queue_status()["processing"] == 2

        # Release both and verify the count drops back
        engine._concurrency_semaphore.release()
        engine._active_job_count -= 1
        engine._concurrency_semaphore.release()
        engine._active_job_count -= 1
        assert engine.get_queue_status()["processing"] == 0

    @pytest.mark.asyncio
    async def test_semaphore_blocks_at_max_concurrent(self):
        """A (max_concurrent_jobs+1)th acquire blocks until a slot is freed (fixes #2299)"""
        engine = ProcessingEngine(max_concurrent_jobs=2)

        # Fill all concurrency slots (mimic start_worker behavior)
        await engine._concurrency_semaphore.acquire()
        engine._active_job_count += 1
        await engine._concurrency_semaphore.acquire()
        engine._active_job_count += 1
        assert engine.get_queue_status()["processing"] == 2

        # The (max+1)th attempt must block — time out to prove it
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(engine._concurrency_semaphore.acquire(), timeout=0.05)

        # After freeing a slot the next acquire should succeed immediately
        engine._concurrency_semaphore.release()
        await asyncio.wait_for(engine._concurrency_semaphore.acquire(), timeout=0.1)

        # Clean up all held slots
        engine._concurrency_semaphore.release()
        engine._concurrency_semaphore.release()


class TestJobDictBoundedMemory:
    """Tests for automatic TTL-based eviction of completed jobs (issue #2216)"""

    def test_completed_job_ttl_parameter_stored(self):
        """completed_job_ttl_hours constructor param is persisted on the engine"""
        engine = ProcessingEngine(max_concurrent_jobs=1, completed_job_ttl_hours=0.5)
        assert engine.completed_job_ttl_hours == 0.5

    def test_default_ttl_is_one_hour(self):
        """Default TTL is 1 hour when not specified"""
        engine = ProcessingEngine()
        assert engine.completed_job_ttl_hours == 1.0

    @pytest.mark.asyncio
    async def test_jobs_dict_stays_bounded_after_many_completions(self, temp_audio_file):
        """Completed jobs are evicted so the dict does not grow without bound"""
        from datetime import datetime, timedelta

        engine = ProcessingEngine(max_concurrent_jobs=2, completed_job_ttl_hours=0.0)

        # Simulate 100 completed jobs whose completed_at is in the past
        for _ in range(100):
            job = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive"},
            )
            job.status = ProcessingStatus.COMPLETED
            job.completed_at = datetime.now() - timedelta(seconds=1)

        assert len(engine.jobs) == 100

        removed = await engine.cleanup_old_jobs(max_age_hours=0.0)

        assert removed == 100
        assert len(engine.jobs) == 0

    @pytest.mark.asyncio
    async def test_active_jobs_are_not_evicted(self, temp_audio_file):
        """QUEUED and PROCESSING jobs must never be removed by cleanup"""
        engine = ProcessingEngine(max_concurrent_jobs=2, completed_job_ttl_hours=0.0)

        queued_job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
        )
        processing_job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
        )
        processing_job.status = ProcessingStatus.PROCESSING

        await engine.cleanup_old_jobs(max_age_hours=0.0)

        assert queued_job.job_id in engine.jobs
        assert processing_job.job_id in engine.jobs

    @pytest.mark.asyncio
    async def test_progress_callbacks_cleaned_up_with_job(self, temp_audio_file):
        """Evicting a job also removes its progress callback to prevent leaks"""
        from datetime import datetime, timedelta

        engine = ProcessingEngine(max_concurrent_jobs=1, completed_job_ttl_hours=0.0)

        job = await engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
        )
        await engine.register_progress_callback(job.job_id, lambda *_: None)
        job.status = ProcessingStatus.COMPLETED
        job.completed_at = datetime.now() - timedelta(seconds=1)

        await engine.cleanup_old_jobs(max_age_hours=0.0)

        assert job.job_id not in engine.jobs
        assert job.job_id not in engine.progress_callbacks


class TestProcessingTimeout:
    """Tests for processing timeout (issue #2747)"""

    def test_default_processing_timeout(self):
        """Default processing timeout is 300 seconds"""
        engine = ProcessingEngine()
        assert engine.processing_timeout == 300.0

    def test_processing_timeout_configurable(self):
        """processing_timeout constructor parameter is stored"""
        engine = ProcessingEngine(processing_timeout=60.0)
        assert engine.processing_timeout == 60.0

    @pytest.mark.asyncio
    async def test_hung_process_times_out_and_fails_job(self, temp_audio_file):
        """A hung processor.process() times out and marks the job FAILED (fixes #2747)"""
        engine = ProcessingEngine(max_concurrent_jobs=1, processing_timeout=0.1)

        with patch('core.job_execution.load_audio') as mock_load, \
             patch('core.processing_engine.HybridProcessor') as mock_processor_cls:

            mock_load.return_value = (np.zeros((1000, 2)), 44100)

            mock_proc = Mock()
            # Simulate a hung DSP call that never returns
            import time
            mock_proc.process.side_effect = lambda *a, **kw: time.sleep(10)
            mock_processor_cls.return_value = mock_proc

            job = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive", "output_format": "wav", "bit_depth": 16},
            )

            await engine.process_job(job)

            assert job.status == ProcessingStatus.FAILED
            assert "timed out" in job.error_message
            assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_timed_out_processor_is_not_cached_for_reuse(self, temp_audio_file):
        """#4727: wait_for only cancels the asyncio-side wrapper future — the
        underlying thread running processor.process() keeps running. The
        timed-out instance must never be returned to the pool for a later
        job with the same config to pop and reuse concurrently."""
        engine = ProcessingEngine(max_concurrent_jobs=1, processing_timeout=0.1)

        with patch('core.job_execution.load_audio') as mock_load, \
             patch('core.processing_engine.HybridProcessor') as mock_processor_cls:

            mock_load.return_value = (np.zeros((1000, 2)), 44100)

            mock_proc = Mock()
            import time
            mock_proc.process.side_effect = lambda *a, **kw: time.sleep(10)
            mock_processor_cls.return_value = mock_proc

            job = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive", "output_format": "wav", "bit_depth": 16},
            )

            await engine.process_job(job)

            assert job.status == ProcessingStatus.FAILED
            # The poisoned instance must not be sitting in the pool.
            assert engine._pool.processors == {}
            # It must have been closed rather than silently dropped.
            mock_proc.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_after_timeout_gets_a_fresh_processor(self, temp_audio_file):
        """#4727 acceptance criterion: a subsequent job with the same
        (mode, config) cache key after a timeout must get a newly-constructed
        processor, not the orphaned one from the timed-out job."""
        engine = ProcessingEngine(max_concurrent_jobs=1, processing_timeout=0.1)

        with patch('core.job_execution.load_audio') as mock_load, \
             patch('core.processing_engine.HybridProcessor') as mock_processor_cls:

            mock_load.return_value = (np.zeros((1000, 2)), 44100)

            import time
            instances = []

            def _make_processor(*a, **kw):
                inst = Mock()
                if len(instances) == 0:
                    # First job's processor: hangs forever (simulates the
                    # orphaned thread still running after wait_for times out).
                    inst.process.side_effect = lambda *a, **kw: time.sleep(10)
                else:
                    inst.process.return_value = np.zeros((1000, 2))
                instances.append(inst)
                return inst

            mock_processor_cls.side_effect = _make_processor

            job1 = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive", "output_format": "wav", "bit_depth": 16},
            )
            await engine.process_job(job1)
            assert job1.status == ProcessingStatus.FAILED

            job2 = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive", "output_format": "wav", "bit_depth": 16},
            )
            await engine.process_job(job2)

            # Two distinct HybridProcessor instances were constructed — the
            # second job never reused the first (poisoned) one.
            assert len(instances) == 2
            assert instances[0] is not instances[1]
            # The first (orphaned) instance was closed, never cached.
            instances[0].close.assert_called_once()


class TestResetProcessorState:
    """Tests for the inter-job reset step in _execute_job (#4797, #4811)."""

    @pytest.mark.asyncio
    async def test_process_job_resets_all_four_stateful_components(self, temp_audio_file):
        """Every job resets EQ, dynamics AND the brick-wall limiter before
        processing — reset_limiter() must be wired in alongside the three
        pre-existing resets (fixes #4811), not just some of them."""
        engine = ProcessingEngine(max_concurrent_jobs=1)

        with patch('core.job_execution.load_audio') as mock_load, \
             patch('core.processing_engine.HybridProcessor') as mock_processor_cls:

            mock_load.return_value = (np.zeros((1000, 2)), 44100)
            mock_proc = Mock()
            mock_proc.process.return_value = np.zeros((1000, 2))
            mock_processor_cls.return_value = mock_proc

            job = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive", "output_format": "wav", "bit_depth": 16},
            )
            await engine.process_job(job)

            assert job.status == ProcessingStatus.COMPLETED
            mock_proc.reset_dynamics.assert_called_once()
            mock_proc.reset_psychoacoustic_eq.assert_called_once()
            mock_proc.reset_limiter.assert_called_once()

    @pytest.mark.asyncio
    async def test_slow_reset_does_not_block_the_event_loop(self, temp_audio_file):
        """The reset step must run off the event loop (fixes #4797): even if
        a reset call blocks for a while (e.g. acquiring `_process_lock`),
        other coroutines scheduled on the loop keep making progress instead
        of the whole process stalling until the reset returns."""
        import threading
        import time

        engine = ProcessingEngine(max_concurrent_jobs=1)

        with patch('core.job_execution.load_audio') as mock_load, \
             patch('core.processing_engine.HybridProcessor') as mock_processor_cls:

            mock_load.return_value = (np.zeros((1000, 2)), 44100)
            mock_proc = Mock()
            mock_proc.process.return_value = np.zeros((1000, 2))
            # Simulate a slow (blocking) acquire of `_process_lock`.
            mock_proc.reset_dynamics.side_effect = lambda: time.sleep(0.3)
            mock_processor_cls.return_value = mock_proc

            job = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive", "output_format": "wav", "bit_depth": 16},
            )

            ticks = 0

            async def _tick_counter():
                nonlocal ticks
                for _ in range(20):
                    await asyncio.sleep(0.01)
                    ticks += 1

            ticker_task = asyncio.create_task(_tick_counter())
            await engine.process_job(job)
            await ticker_task

            # If the reset call blocked the event loop directly, the ticker
            # would have starved while the 0.3s sleep ran on the loop thread.
            assert ticks == 20
            assert job.status == ProcessingStatus.COMPLETED


class TestSafeErrorMessageModuleError:
    """#4769: ModuleError never matched _ERROR_CATEGORIES, so every audio-load
    failure (missing file, unsupported format, FFmpeg timeout, truncated
    file...) collapsed into the generic catch-all message."""

    def test_file_not_found_maps_to_specific_message(self):
        from auralis.utils.logging import Code, ModuleError

        exc = ModuleError(f"{Code.ERROR_FILE_NOT_FOUND}: /some/absolute/path.wav")
        message = _safe_error_message(exc)

        assert message == "Audio file not found"
        assert message != "An unexpected error occurred during processing"

    @pytest.mark.parametrize(
        "code_attr,expected_message",
        [
            ("ERROR_FILE_NOT_FOUND", "Audio file not found"),
            ("ERROR_EMPTY_FILE", "Audio file is empty"),
            ("ERROR_EMPTY_AUDIO", "Audio file contains no audio data"),
            ("ERROR_UNSUPPORTED_FORMAT", "Unsupported audio format"),
            ("ERROR_INVALID_SAMPLE_RATE", "Invalid audio sample rate"),
            ("ERROR_INVALID_AUDIO", "Invalid or corrupted audio data"),
            ("ERROR_TRUNCATED_FILE", "Audio file appears to be truncated or incomplete"),
            ("ERROR_CORRUPTED", "Audio file is corrupted or unsupported"),
            ("ERROR_FFMPEG_NOT_FOUND", "Audio decoder unavailable on server"),
            ("ERROR_FFMPEG_TIMEOUT", "Audio conversion timed out"),
            ("ERROR_FFMPEG_CONVERSION", "Audio file could not be converted"),
            ("ERROR_LOADING", "Audio file could not be loaded"),
        ],
    )
    def test_each_module_error_code_maps_to_distinct_message(
        self, code_attr, expected_message
    ):
        from auralis.utils.logging import Code, ModuleError

        code_value = getattr(Code, code_attr)
        exc = ModuleError(f"{code_value}: some detail")

        assert _safe_error_message(exc) == expected_message

    def test_unknown_module_error_code_falls_back_safely(self):
        from auralis.utils.logging import ModuleError

        exc = ModuleError("No audio stream found")

        assert _safe_error_message(exc) == "Audio file could not be processed"

    def test_module_error_never_leaks_raw_path_or_stderr(self):
        """The raw code text (absolute paths, FFmpeg stderr) must never be
        passed through — only the mapped category string is returned."""
        from auralis.utils.logging import Code, ModuleError

        leaky_detail = "/home/deploy/secret/tracks/original_master.wav"
        exc = ModuleError(f"{Code.ERROR_FILE_NOT_FOUND}: {leaky_detail}")

        message = _safe_error_message(exc)

        assert leaky_detail not in message
        assert "/home/" not in message


class TestIgnoredSettingsSurfaced:
    """#5060: eq/dynamics/level_matching/genre_override/sample_rate are
    accepted and validated by the API but not consumed by the offline
    pipeline — _create_processor_config must surface exactly which ones were
    ignored on the job, and it must reach result_data so a client can tell
    "applied" from "silently ignored"."""

    def test_eq_enabled_is_reported_ignored(self, engine):
        job = ProcessingJob(
            job_id="j1", input_path="in.wav", output_path="out.wav",
            settings={"mode": "adaptive", "eq": {"enabled": True}},
        )
        engine._create_processor_config(job)
        assert job.ignored_settings == ["eq"]

    def test_dynamics_and_level_matching_enabled_are_reported(self, engine):
        job = ProcessingJob(
            job_id="j2", input_path="in.wav", output_path="out.wav",
            settings={
                "mode": "adaptive",
                "dynamics": {"enabled": True},
                "level_matching": {"enabled": True},
            },
        )
        engine._create_processor_config(job)
        assert set(job.ignored_settings) == {"dynamics", "level_matching"}

    def test_eq_present_but_disabled_is_not_reported(self, engine):
        """Matches the eq/dynamics/level_matching contract: presence alone
        isn't enough, "enabled" must be truthy."""
        job = ProcessingJob(
            job_id="j3", input_path="in.wav", output_path="out.wav",
            settings={"mode": "adaptive", "eq": {"enabled": False}},
        )
        engine._create_processor_config(job)
        assert job.ignored_settings == []

    def test_genre_override_set_is_reported(self, engine):
        job = ProcessingJob(
            job_id="j4", input_path="in.wav", output_path="out.wav",
            settings={"mode": "adaptive", "genre_override": "rock"},
        )
        engine._create_processor_config(job)
        assert job.ignored_settings == ["genre_override"]

    def test_genre_override_defaulted_to_none_is_not_reported(self):
        """Regression for the presence-check bug this fix corrects:
        ProcessingSettings.model_dump() always includes "genre_override"
        with a None default even when the client never set it, so
        `"genre_override" in job.settings` was True — and thus reported as
        ignored — on EVERY job, not just ones that actually requested it."""
        engine = ProcessingEngine(max_concurrent_jobs=1)
        job = ProcessingJob(
            job_id="j5", input_path="in.wav", output_path="out.wav",
            settings={"mode": "adaptive", "genre_override": None},
        )
        engine._create_processor_config(job)
        assert job.ignored_settings == []

    def test_non_default_sample_rate_is_reported(self, engine):
        job = ProcessingJob(
            job_id="j6", input_path="in.wav", output_path="out.wav",
            settings={"mode": "adaptive", "sample_rate": 96000},
        )
        engine._create_processor_config(job)
        assert job.ignored_settings == ["sample_rate"]

    def test_sample_rate_none_keeps_original_and_is_not_reported(self, engine):
        job = ProcessingJob(
            job_id="j7", input_path="in.wav", output_path="out.wav",
            settings={"mode": "adaptive", "sample_rate": None},
        )
        engine._create_processor_config(job)
        assert job.ignored_settings == []

    @pytest.mark.asyncio
    async def test_completed_job_result_data_lists_ignored_settings(self, temp_audio_file):
        """End-to-end: a client reading result_data must see the gap without
        parsing server logs."""
        engine = ProcessingEngine(max_concurrent_jobs=1)

        with patch('core.job_execution.load_audio') as mock_load, \
             patch('core.processing_engine.HybridProcessor') as mock_processor, \
             patch('core.job_execution.save') as mock_save:

            mock_load.return_value = (np.zeros((1000, 2), dtype=np.float32), 44100)
            mock_proc_instance = Mock()
            mock_proc_instance.process.return_value = np.zeros((1000, 2), dtype=np.float32)
            mock_proc_instance.last_content_profile = {}
            mock_proc_instance.continuous_mode.last_fingerprint = None
            mock_processor.return_value = mock_proc_instance

            job = await engine.create_job(
                input_path=str(temp_audio_file),
                settings={
                    "mode": "adaptive",
                    "output_format": "wav",
                    "bit_depth": 16,
                    "eq": {"enabled": True},
                    "sample_rate": 96000,
                },
            )
            await engine.process_job(job)

            assert job.status == ProcessingStatus.COMPLETED
            assert job.result_data is not None
            assert set(job.result_data["ignored_settings"]) == {"eq", "sample_rate"}
            mock_save.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])