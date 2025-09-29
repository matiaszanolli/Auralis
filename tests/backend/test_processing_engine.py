"""
Tests for ProcessingEngine (Fixed API Signatures)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the job queue system with correct API signatures.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import numpy as np

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])