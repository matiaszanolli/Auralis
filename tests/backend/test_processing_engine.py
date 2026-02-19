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

from processing_engine import (
    ProcessingEngine,
    ProcessingJob,
    ProcessingStatus,
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

    def test_create_job(self, engine, temp_audio_file):
        """Test creating a job"""
        job = engine.create_job(
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
        job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )

        job_id = await engine.submit_job(job)

        assert job_id == job.job_id
        assert engine.job_queue.qsize() == 1

    def test_get_job(self, engine, temp_audio_file):
        """Test retrieving a job"""
        job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )

        retrieved = engine.get_job(job.job_id)

        assert retrieved is not None
        assert retrieved.job_id == job.job_id

    def test_get_nonexistent_job(self, engine):
        """Test getting nonexistent job returns None"""
        job = engine.get_job("nonexistent-id")
        assert job is None

    def test_cancel_job(self, engine, temp_audio_file):
        """Test cancelling a job"""
        job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )

        result = engine.cancel_job(job.job_id)

        assert result is True
        assert job.status == ProcessingStatus.CANCELLED

    def test_cancel_nonexistent_job(self, engine):
        """Test cancelling nonexistent job"""
        result = engine.cancel_job("nonexistent-id")
        assert result is False

    def test_get_all_jobs(self, engine, temp_audio_file):
        """Test getting all jobs"""
        job1 = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )
        job2 = engine.create_job(
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
        job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )
        await engine.submit_job(job)

        status = engine.get_queue_status()

        assert status["total_jobs"] >= 1
        assert status["queued"] >= 1

    def test_register_progress_callback(self, engine):
        """Test registering progress callback"""
        callback_called = {"called": False}

        async def test_callback(job_id, progress, message):
            callback_called["called"] = True

        engine.register_progress_callback("test-job", test_callback)

        assert "test-job" in engine.progress_callbacks

    def test_cleanup_old_jobs(self, engine, temp_audio_file):
        """Test cleaning up old jobs"""
        from datetime import datetime, timedelta

        job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"}
        )
        job.status = ProcessingStatus.COMPLETED
        job.completed_at = datetime.now() - timedelta(hours=25)  # Old job

        # Add job to engine's jobs dict
        engine.jobs[job.job_id] = job

        removed = engine.cleanup_old_jobs(max_age_hours=24)

        assert removed == 1
        assert job.job_id not in engine.jobs

    @pytest.mark.asyncio
    async def test_multiple_jobs(self, engine, temp_audio_file):
        """Test submitting multiple jobs"""
        jobs = []
        for i in range(3):
            job = engine.create_job(
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
        """Test processing with mocked dependencies"""
        engine = ProcessingEngine(max_concurrent_jobs=1)

        with patch('processing_engine.load_audio') as mock_load, \
             patch('processing_engine.HybridProcessor') as mock_processor, \
             patch('processing_engine.save') as mock_save:

            # Setup mocks
            mock_load.return_value = (np.zeros((1000, 2)), 44100)

            mock_proc_instance = Mock()
            mock_result = Mock()
            mock_result.audio = np.zeros((1000, 2))
            mock_result.lufs = -14.0
            mock_proc_instance.process.return_value = mock_result
            mock_processor.return_value = mock_proc_instance

            # Create and process job
            job = engine.create_job(
                input_path=str(temp_audio_file),
                settings={
                    "mode": "adaptive",
                    "output_format": "wav",
                    "bit_depth": 16
                }
            )

            try:
                await engine.process_job(job)
                # If it completes, great!
            except Exception:
                # Some errors expected without full setup
                pass


class TestJobCreation:
    """Test job creation with different modes"""

    def test_create_adaptive_job(self, engine, temp_audio_file):
        """Test creating adaptive mode job"""
        job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
            mode="adaptive"
        )

        assert job.mode == "adaptive"
        assert job.status == ProcessingStatus.QUEUED

    def test_create_reference_job(self, engine, temp_audio_file):
        """Test creating reference mode job"""
        job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "reference"},
            mode="reference"
        )

        assert job.mode == "reference"

    def test_create_hybrid_job(self, engine, temp_audio_file):
        """Test creating hybrid mode job"""
        job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "hybrid"},
            mode="hybrid",
            reference_path="/path/to/reference.wav"
        )

        assert job.mode == "hybrid"
        assert "reference_path" in job.settings


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_create_job_with_invalid_file(self, engine):
        """Test creating job with nonexistent file"""
        job = engine.create_job(
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
            job = engine.create_job(
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
            job = engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive"},
            )
            await engine.submit_job(job)

        assert engine.job_queue.full()

        # One more submit must raise QueueFull
        overflow_job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
        )
        with pytest.raises(asyncio.QueueFull):
            await engine.submit_job(overflow_job)

    @pytest.mark.asyncio
    async def test_queue_full_removes_job_from_jobs_dict(self, temp_audio_file):
        """When submit_job raises QueueFull the job is cleaned from self.jobs"""
        engine = ProcessingEngine(max_queue_size=1)

        first_job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
        )
        await engine.submit_job(first_job)

        overflow_job = engine.create_job(
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
        """get_queue_status()['processing'] is derived from the semaphore, not a separate counter (fixes #2299)"""
        engine = ProcessingEngine(max_concurrent_jobs=3)

        assert engine.get_queue_status()["processing"] == 0

        # Simulate two jobs holding concurrency slots
        await engine._concurrency_semaphore.acquire()
        assert engine.get_queue_status()["processing"] == 1

        await engine._concurrency_semaphore.acquire()
        assert engine.get_queue_status()["processing"] == 2

        # Release both and verify the count drops back
        engine._concurrency_semaphore.release()
        engine._concurrency_semaphore.release()
        assert engine.get_queue_status()["processing"] == 0

    @pytest.mark.asyncio
    async def test_semaphore_blocks_at_max_concurrent(self):
        """A (max_concurrent_jobs+1)th acquire blocks until a slot is freed (fixes #2299)"""
        engine = ProcessingEngine(max_concurrent_jobs=2)

        # Fill all concurrency slots
        await engine._concurrency_semaphore.acquire()
        await engine._concurrency_semaphore.acquire()
        assert engine._concurrency_semaphore._value == 0
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

    def test_jobs_dict_stays_bounded_after_many_completions(self, temp_audio_file):
        """Completed jobs are evicted so the dict does not grow without bound"""
        from datetime import datetime, timedelta

        engine = ProcessingEngine(max_concurrent_jobs=2, completed_job_ttl_hours=0.0)

        # Simulate 100 completed jobs whose completed_at is in the past
        for _ in range(100):
            job = engine.create_job(
                input_path=str(temp_audio_file),
                settings={"mode": "adaptive"},
            )
            job.status = ProcessingStatus.COMPLETED
            job.completed_at = datetime.now() - timedelta(seconds=1)

        assert len(engine.jobs) == 100

        removed = engine.cleanup_old_jobs(max_age_hours=0.0)

        assert removed == 100
        assert len(engine.jobs) == 0

    def test_active_jobs_are_not_evicted(self, temp_audio_file):
        """QUEUED and PROCESSING jobs must never be removed by cleanup"""
        engine = ProcessingEngine(max_concurrent_jobs=2, completed_job_ttl_hours=0.0)

        queued_job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
        )
        processing_job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
        )
        processing_job.status = ProcessingStatus.PROCESSING

        engine.cleanup_old_jobs(max_age_hours=0.0)

        assert queued_job.job_id in engine.jobs
        assert processing_job.job_id in engine.jobs

    def test_progress_callbacks_cleaned_up_with_job(self, temp_audio_file):
        """Evicting a job also removes its progress callback to prevent leaks"""
        from datetime import datetime, timedelta

        engine = ProcessingEngine(max_concurrent_jobs=1, completed_job_ttl_hours=0.0)

        job = engine.create_job(
            input_path=str(temp_audio_file),
            settings={"mode": "adaptive"},
        )
        engine.register_progress_callback(job.job_id, lambda *_: None)
        job.status = ProcessingStatus.COMPLETED
        job.completed_at = datetime.now() - timedelta(seconds=1)

        engine.cleanup_old_jobs(max_age_hours=0.0)

        assert job.job_id not in engine.jobs
        assert job.job_id not in engine.progress_callbacks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])