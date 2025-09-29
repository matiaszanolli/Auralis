"""
Tests for Processing API
~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the FastAPI REST endpoints for audio processing.
"""

import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import json
import io

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from processing_api import router, set_processing_engine
from processing_engine import ProcessingEngine, ProcessingJob, ProcessingStatus
from fastapi import FastAPI


@pytest.fixture
def app():
    """Create FastAPI app with processing router"""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_engine():
    """Create mock processing engine"""
    engine = Mock(spec=ProcessingEngine)
    engine.submit_job = AsyncMock(return_value="test-job-123")

    # Create a mock job object that behaves like ProcessingJob
    mock_job = Mock()
    mock_job.job_id = "test-job-123"
    mock_job.status = ProcessingStatus.QUEUED
    mock_job.progress = 0.0
    mock_job.error_message = None
    mock_job.result_data = {}

    engine.get_job = Mock(return_value=mock_job)
    engine.cancel_job = Mock(return_value=True)  # Synchronous, not async
    engine.get_all_jobs = Mock(return_value=[])
    engine.get_queue_status = Mock(return_value={
        "total_jobs": 0,
        "queued": 0,
        "processing": 0,
        "completed": 0,
        "failed": 0,
        "max_concurrent": 2
    })
    engine.cleanup_old_jobs = Mock(return_value=5)  # Synchronous, not async

    set_processing_engine(engine)
    return engine


class TestProcessingPresets:
    """Test preset endpoints"""

    def test_get_presets(self, client, mock_engine):
        """Test getting processing presets"""
        response = client.get("/api/processing/presets")

        assert response.status_code == 200
        data = response.json()

        assert "presets" in data
        assert "adaptive" in data["presets"]
        assert "gentle" in data["presets"]
        assert "warm" in data["presets"]
        assert "bright" in data["presets"]
        assert "punchy" in data["presets"]

    def test_preset_structure(self, client, mock_engine):
        """Test preset data structure"""
        response = client.get("/api/processing/presets")
        data = response.json()

        adaptive = data["presets"]["adaptive"]

        assert "name" in adaptive
        assert "description" in adaptive
        assert "mode" in adaptive
        assert "settings" in adaptive

        assert adaptive["mode"] == "adaptive"


class TestJobSubmission:
    """Test job submission endpoints"""

    def test_upload_and_process(self, client, mock_engine):
        """Test upload and process endpoint"""
        # Create fake audio file
        audio_data = b"RIFF" + b"\x00" * 40  # Minimal WAV header
        files = {"file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        data = {"settings": json.dumps({"mode": "adaptive"})}

        response = client.post(
            "/api/processing/upload-and-process",
            files=files,
            data=data
        )

        assert response.status_code == 200
        result = response.json()

        assert "job_id" in result
        assert result["job_id"] == "test-job-123"
        assert mock_engine.submit_job.called

    def test_upload_without_file(self, client, mock_engine):
        """Test upload endpoint without file"""
        data = {"settings": json.dumps({"mode": "adaptive"})}

        response = client.post(
            "/api/processing/upload-and-process",
            data=data
        )

        assert response.status_code == 422  # Validation error


class TestJobStatus:
    """Test job status endpoints"""

    def test_get_job_status(self, client, mock_engine):
        """Test getting job status"""
        response = client.get("/api/processing/job/test-job-123")

        assert response.status_code == 200
        data = response.json()

        assert data["job_id"] == "test-job-123"
        assert data["status"] == "queued"
        assert "progress" in data

    def test_get_nonexistent_job(self, client, mock_engine):
        """Test getting status of nonexistent job"""
        mock_engine.get_job.return_value = None

        response = client.get("/api/processing/job/nonexistent-job")

        assert response.status_code == 404

    def test_cancel_job(self, client, mock_engine):
        """Test cancelling a job"""
        response = client.post("/api/processing/job/test-job-123/cancel")

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert mock_engine.cancel_job.called

    def test_cancel_nonexistent_job(self, client, mock_engine):
        """Test cancelling nonexistent job"""
        mock_engine.cancel_job.return_value = False
        mock_engine.get_job.return_value = None  # Job doesn't exist

        response = client.post("/api/processing/job/nonexistent-job/cancel")

        assert response.status_code == 404


class TestJobDownload:
    """Test job download endpoints"""

    def test_download_completed_job(self, client, mock_engine, tmp_path):
        """Test downloading completed job result"""
        # Create a real temp file for download
        test_file = tmp_path / "test_output.wav"
        test_file.write_bytes(b"audio_data")

        # Mock completed job with output file
        mock_job = Mock()
        mock_job.job_id = "test-job-123"
        mock_job.status = ProcessingStatus.COMPLETED
        mock_job.output_path = str(test_file)

        mock_engine.get_job.return_value = mock_job

        response = client.get("/api/processing/job/test-job-123/download")

        assert response.status_code == 200
        assert b"audio_data" in response.content

    def test_download_incomplete_job(self, client, mock_engine):
        """Test downloading incomplete job"""
        mock_job = Mock()
        mock_job.job_id = "test-job-123"
        mock_job.status = ProcessingStatus.PROCESSING
        mock_job.progress = 50.0

        mock_engine.get_job.return_value = mock_job

        response = client.get("/api/processing/job/test-job-123/download")

        assert response.status_code == 400  # Job not completed


class TestQueueManagement:
    """Test queue management endpoints"""

    def test_get_queue_status(self, client, mock_engine):
        """Test getting queue status"""
        response = client.get("/api/processing/queue/status")

        assert response.status_code == 200
        data = response.json()

        assert "total_jobs" in data
        assert "queued" in data
        assert "processing" in data
        assert "completed" in data
        assert "failed" in data
        assert "max_concurrent" in data

    def test_list_all_jobs(self, client, mock_engine):
        """Test listing all jobs"""
        # Create mock job objects with to_dict method
        mock_job1 = Mock()
        mock_job1.job_id = "job-1"
        mock_job1.status = ProcessingStatus.COMPLETED
        mock_job1.to_dict.return_value = {"job_id": "job-1", "status": "completed"}

        mock_job2 = Mock()
        mock_job2.job_id = "job-2"
        mock_job2.status = ProcessingStatus.PROCESSING
        mock_job2.to_dict.return_value = {"job_id": "job-2", "status": "processing"}

        mock_engine.get_all_jobs.return_value = [mock_job1, mock_job2]

        response = client.get("/api/processing/jobs")

        assert response.status_code == 200
        data = response.json()

        assert "jobs" in data
        assert len(data["jobs"]) == 2

    def test_cleanup_old_jobs(self, client, mock_engine):
        """Test cleaning up old jobs"""
        response = client.delete("/api/processing/jobs/cleanup?max_age_hours=24")

        assert response.status_code == 200
        data = response.json()

        assert "removed" in data
        assert data["removed"] == 5
        assert mock_engine.cleanup_old_jobs.called


class TestProcessingSettings:
    """Test processing settings validation"""

    def test_valid_settings(self, client, mock_engine):
        """Test with valid processing settings"""
        audio_data = b"RIFF" + b"\x00" * 40
        files = {"file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}

        settings = {
            "mode": "adaptive",
            "output_format": "wav",
            "bit_depth": 16,
            "eq": {"enabled": True},
            "dynamics": {"enabled": True},
            "levelMatching": {"enabled": True, "targetLufs": -16}
        }

        data = {"settings": json.dumps(settings)}

        response = client.post(
            "/api/processing/upload-and-process",
            files=files,
            data=data
        )

        assert response.status_code == 200

    def test_settings_with_custom_eq(self, client, mock_engine):
        """Test settings with custom EQ values"""
        audio_data = b"RIFF" + b"\x00" * 40
        files = {"file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}

        settings = {
            "mode": "adaptive",
            "eq": {
                "enabled": True,
                "low": 2,
                "lowMid": 1,
                "mid": 0,
                "highMid": 1,
                "high": 2
            }
        }

        data = {"settings": json.dumps(settings)}

        response = client.post(
            "/api/processing/upload-and-process",
            files=files,
            data=data
        )

        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling"""

    def test_engine_not_initialized(self, client):
        """Test when engine is not initialized"""
        set_processing_engine(None)

        response = client.get("/api/processing/queue/status")

        assert response.status_code == 503  # Service unavailable

    def test_invalid_json_settings(self, client, mock_engine):
        """Test with invalid JSON in settings"""
        audio_data = b"RIFF" + b"\x00" * 40
        files = {"file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        data = {"settings": "invalid-json"}

        response = client.post(
            "/api/processing/upload-and-process",
            files=files,
            data=data
        )

        # Should handle JSON parsing error
        assert response.status_code in [400, 422, 500]


class TestPresetApplication:
    """Test applying presets"""

    def test_apply_gentle_preset(self, client, mock_engine):
        """Test applying gentle preset"""
        audio_data = b"RIFF" + b"\x00" * 40
        files = {"file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}

        # Get gentle preset settings
        presets_response = client.get("/api/processing/presets")
        presets = presets_response.json()["presets"]
        gentle_settings = presets["gentle"]["settings"]

        data = {"settings": json.dumps(gentle_settings)}

        response = client.post(
            "/api/processing/upload-and-process",
            files=files,
            data=data
        )

        assert response.status_code == 200

    def test_all_presets_valid(self, client, mock_engine):
        """Test that all presets have valid structure"""
        response = client.get("/api/processing/presets")
        presets = response.json()["presets"]

        for preset_name, preset_data in presets.items():
            assert "name" in preset_data
            assert "description" in preset_data
            assert "mode" in preset_data
            assert "settings" in preset_data

            # Settings should have eq, dynamics, and levelMatching
            settings = preset_data["settings"]
            assert "eq" in settings
            assert "dynamics" in settings


if __name__ == "__main__":
    pytest.main([__file__, "-v"])