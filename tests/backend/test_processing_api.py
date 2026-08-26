"""
Tests for Processing API
~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the FastAPI REST endpoints for audio processing.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from fastapi import FastAPI
from routers.processing_api import create_processing_router, _is_valid_audio_magic
from core.processing_engine import ProcessingEngine, ProcessingJob, ProcessingStatus


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

    engine.get_job = AsyncMock(return_value=mock_job)
    engine.cancel_job = AsyncMock(return_value=True)
    engine.get_all_jobs = Mock(return_value=[])
    engine.get_queue_status = Mock(return_value={
        "total_jobs": 0,
        "queued": 0,
        "processing": 0,
        "completed": 0,
        "failed": 0,
        "max_concurrent": 2
    })
    engine.cleanup_old_jobs = AsyncMock(return_value=5)
    return engine


@pytest.fixture
def app(mock_engine):
    """Create FastAPI app with processing router using factory pattern (#3862)."""
    test_app = FastAPI()
    test_app.include_router(create_processing_router(lambda: mock_engine))
    return test_app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


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

    def test_presets_match_the_engines_profiles(self, client, mock_engine):
        """Every value comes from create_preset_profiles(), in its units (#5220).

        The endpoint used to return a hand-typed dict whose EQ and compressor
        numbers were invented — unitless integers matching nothing the
        mastering engine applies (`gentle` advertised ratio 2 @ -24 dB where
        the engine uses 1.8 @ -20.0 dB) — and it silently dropped the 6th
        preset. Asserted field-by-field against the profiles so a future edit
        to either side has to touch this test.
        """
        from auralis.core.config.preset_profiles import create_preset_profiles

        profiles = create_preset_profiles()
        presets = client.get("/api/processing/presets").json()["presets"]

        assert set(presets) == set(profiles), "endpoint and engine disagree on the catalog"
        assert "live" in presets, "the engine's 6th preset must not be dropped"

        for name, profile in profiles.items():
            payload = presets[name]
            assert payload["name"] == profile.name
            assert payload["description"] == profile.description

            eq = payload["settings"]["eq"]
            assert eq["low"] == profile.low_shelf_gain
            assert eq["low_mid"] == profile.low_mid_gain
            assert eq["mid"] == profile.mid_gain
            assert eq["high_mid"] == profile.high_mid_gain
            assert eq["high"] == profile.high_shelf_gain
            assert eq["blend"] == profile.eq_blend

            comp = payload["settings"]["dynamics"]["compressor"]
            assert comp["threshold"] == profile.compression_threshold
            assert comp["ratio"] == profile.compression_ratio
            assert comp["attack"] == profile.compression_attack
            assert comp["release"] == profile.compression_release

            limiter = payload["settings"]["dynamics"]["limiter"]
            assert limiter["threshold"] == profile.limiter_threshold
            assert limiter["release"] == profile.limiter_release

            level = payload["settings"]["level_matching"]
            assert level["target_lufs"] == profile.target_lufs
            assert level["peak_target_db"] == profile.peak_target_db

    def test_preset_gains_are_db_not_unitless_ints(self, client, mock_engine):
        """Pins the unit change specifically (#5220).

        The fabricated payload used small unitless integers; the engine's are
        dB gains and real thresholds. `gentle` is the clearest case.
        """
        gentle = client.get("/api/processing/presets").json()["presets"]["gentle"]

        assert gentle["settings"]["eq"]["low"] == 0.3          # was 1
        assert gentle["settings"]["eq"]["high"] == 0.5         # was 2
        assert gentle["settings"]["dynamics"]["compressor"]["ratio"] == 1.8      # was 2
        assert gentle["settings"]["dynamics"]["compressor"]["threshold"] == -20.0  # was -24

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

    def test_preset_keys_are_all_snake_case(self, client, mock_engine):
        """Every key in the presets payload is snake_case (#3895).

        The dict literals mixed `targetLufs`, `lowMid` and `highMid` into a
        payload that is otherwise snake_case (`level_matching`, `attack`,
        `release`, `threshold`, `ratio`). Nothing caught it because the response
        model is `presets: dict[str, Any]` and the settings sub-dicts are
        `dict[str, Any]` all the way to the engine, so the keys are opaque
        end to end -- no consumer would have failed on the mismatch either.

        Asserted over the whole tree rather than the three known names so a new
        camelCase key in a future preset fails here too.
        """
        response = client.get("/api/processing/presets")
        assert response.status_code == 200

        offenders: list[str] = []

        def walk(node: object, path: str) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    # Preset ids and display names are values, not field names;
                    # only dict KEYS are part of the wire contract.
                    if any(ch.isupper() for ch in key):
                        offenders.append(f"{path}.{key}")
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    walk(item, f"{path}[{i}]")

        walk(response.json()["presets"], "presets")
        assert offenders == [], f"camelCase keys in presets payload: {offenders}"

    def test_preset_eq_bands_use_snake_case_names(self, client, mock_engine):
        """The specific renames, pinned by name (#3895)."""
        response = client.get("/api/processing/presets")
        presets = response.json()["presets"]

        gentle_eq = presets["gentle"]["settings"]["eq"]
        assert "low_mid" in gentle_eq
        assert "high_mid" in gentle_eq
        assert "lowMid" not in gentle_eq
        assert "highMid" not in gentle_eq

        level_matching = presets["adaptive"]["settings"]["level_matching"]
        assert "target_lufs" in level_matching
        assert "targetLufs" not in level_matching


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

    def test_download_completed_job_with_no_output_path(self, client, mock_engine):
        """#4736: a job that reached COMPLETED without output_path set must
        raise a typed 500, not an unhandled TypeError from Path(None)."""
        mock_job = Mock()
        mock_job.job_id = "test-job-123"
        mock_job.status = ProcessingStatus.COMPLETED
        mock_job.output_path = None

        mock_engine.get_job.return_value = mock_job

        response = client.get("/api/processing/job/test-job-123/download")

        assert response.status_code == 500
        assert "detail" in response.json()


class TestFiveHandlersHaveErrorHandling:
    """#4736: get_job_status, download_result, cancel_job, list_jobs, and
    get_queue_status must convert an unexpected engine-layer exception into
    a typed {"detail": ...} 500, not let it propagate as Starlette's bare
    unhandled-exception response."""

    def test_get_job_status_unexpected_exception_yields_typed_500(self, client, mock_engine):
        mock_engine.get_job.side_effect = RuntimeError("engine exploded")
        response = client.get("/api/processing/job/test-job-123")
        assert response.status_code == 500
        assert "detail" in response.json()

    def test_download_result_unexpected_exception_yields_typed_500(self, client, mock_engine):
        mock_engine.get_job.side_effect = RuntimeError("engine exploded")
        response = client.get("/api/processing/job/test-job-123/download")
        assert response.status_code == 500
        assert "detail" in response.json()

    def test_cancel_job_unexpected_exception_yields_typed_500(self, client, mock_engine):
        mock_engine.cancel_job.side_effect = RuntimeError("engine exploded")
        response = client.post("/api/processing/job/test-job-123/cancel")
        assert response.status_code == 500
        assert "detail" in response.json()

    def test_list_jobs_unexpected_exception_yields_typed_500(self, client, mock_engine):
        mock_engine.get_all_jobs.side_effect = RuntimeError("engine exploded")
        response = client.get("/api/processing/jobs")
        assert response.status_code == 500
        assert "detail" in response.json()

    def test_get_queue_status_unexpected_exception_yields_typed_500(self, client, mock_engine):
        mock_engine.get_queue_status.side_effect = RuntimeError("engine exploded")
        response = client.get("/api/processing/queue/status")
        assert response.status_code == 500
        assert "detail" in response.json()


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

    def test_list_jobs_rejects_negative_limit(self, client, mock_engine):
        """Negative limit must return 422 (fixes #2729)"""
        response = client.get("/api/processing/jobs?limit=-1")
        assert response.status_code == 422

    def test_list_jobs_rejects_zero_limit(self, client, mock_engine):
        """Zero limit must return 422"""
        response = client.get("/api/processing/jobs?limit=0")
        assert response.status_code == 422

    def test_list_jobs_rejects_excessive_limit(self, client, mock_engine):
        """Limit above 1000 must return 422"""
        response = client.get("/api/processing/jobs?limit=9999")
        assert response.status_code == 422

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


class TestOutputFormatBitDepthValidation:
    """#4746: output_format/bit_depth were unvalidated free str/int fields
    whose docstring advertised (format, bit_depth) combinations libsndfile
    cannot actually write (verified against soundfile.available_subtypes:
    FLAC has no 32-bit PCM subtype; MP3 has no PCM subtype at all). A bad
    combination used to reach libsndfile and fail deep inside the save step
    as a generic, misleading job failure instead of a 422 at submission."""

    @pytest.mark.parametrize("output_format,bit_depth", [
        ("wav", 16), ("wav", 24), ("wav", 32),
        ("flac", 16), ("flac", 24),
    ])
    def test_valid_combinations_are_accepted(
        self, client, mock_engine, tmp_path, output_format, bit_depth
    ):
        audio_file = tmp_path / "song.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)
        mock_engine.create_job.return_value = mock_engine.get_job.return_value

        with patch("routers.processing_api.validate_file_path", return_value=audio_file):
            response = client.post(
                "/api/processing/process",
                json={
                    "input_path": str(audio_file),
                    "settings": {"output_format": output_format, "bit_depth": bit_depth},
                },
            )

        assert response.status_code == 200, response.json()

    def test_unrecognized_output_format_rejected_with_422(self, client, mock_engine, tmp_path):
        audio_file = tmp_path / "song.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

        response = client.post(
            "/api/processing/process",
            json={"input_path": str(audio_file), "settings": {"output_format": "ogg"}},
        )

        assert response.status_code == 422
        mock_engine.create_job.assert_not_called()

    def test_unrecognized_bit_depth_rejected_with_422(self, client, mock_engine, tmp_path):
        audio_file = tmp_path / "song.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

        response = client.post(
            "/api/processing/process",
            json={"input_path": str(audio_file), "settings": {"bit_depth": 8}},
        )

        assert response.status_code == 422
        mock_engine.create_job.assert_not_called()

    def test_flac_32bit_combo_rejected_with_specific_message(self, client, mock_engine, tmp_path):
        """FLAC's maximum PCM subtype is 24-bit — 32 is a real Literal value
        (valid for wav) but an invalid combination with flac."""
        audio_file = tmp_path / "song.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

        response = client.post(
            "/api/processing/process",
            json={
                "input_path": str(audio_file),
                "settings": {"output_format": "flac", "bit_depth": 32},
            },
        )

        assert response.status_code == 422
        mock_engine.create_job.assert_not_called()
        detail = json.dumps(response.json())
        assert "flac" in detail.lower() and "32" in detail

    def test_mp3_rejected_regardless_of_bit_depth(self, client, mock_engine, tmp_path):
        """MP3 has no PCM subtype at all, so every (mp3, bit_depth)
        combination is currently unsupported by the save pipeline."""
        audio_file = tmp_path / "song.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

        response = client.post(
            "/api/processing/process",
            json={"input_path": str(audio_file), "settings": {"output_format": "mp3"}},
        )

        assert response.status_code == 422
        mock_engine.create_job.assert_not_called()
        detail = json.dumps(response.json())
        assert "mp3" in detail.lower()

    def test_upload_and_process_surfaces_invalid_combo_as_400(self, client, mock_engine):
        """upload-and-process parses settings manually (not via FastAPI's
        automatic body validation), so a ValidationError from the same
        model_validator surfaces as 400 there instead of 422 — pre-existing
        behavior for this route (see the ValidationError catch a few lines
        above), unaffected by this fix beyond now actually catching the bad
        combination in the first place."""
        audio_data = b"RIFF" + b"\x00" * 40
        files = {"file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        data = {"settings": json.dumps({"output_format": "mp3"})}

        response = client.post(
            "/api/processing/upload-and-process",
            files=files,
            data=data,
        )

        assert response.status_code == 400
        assert "mp3" in response.json()["detail"].lower()


class TestErrorHandling:
    """Test error handling"""

    def test_engine_not_initialized(self):
        """Test when engine is not initialized — factory with None getter returns 503."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        null_app = FastAPI()
        null_app.include_router(create_processing_router(lambda: None))
        null_client = TestClient(null_app)

        response = null_client.get("/api/processing/queue/status")

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

        # Client sent malformed JSON — a well-behaved endpoint rejects this as
        # a 400 Bad Request, not a 500 (#4788). NOTE: the router currently
        # lets json.JSONDecodeError fall through to the generic `except
        # Exception` handler and returns 500 instead — see final report.
        assert response.status_code == 400


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


class TestQueueBackpressureAPI:
    """Tests for 503 responses when the processing queue is full (issue #2332)"""

    def test_process_returns_503_when_queue_full(self, client, mock_engine, tmp_path):
        """POST /api/processing/process returns 503 when submit_job raises QueueFull"""
        import asyncio

        mock_engine.submit_job = AsyncMock(side_effect=asyncio.QueueFull())

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)
        mock_engine.create_job.return_value = mock_engine.get_job.return_value

        # Bypass path validation so the request reaches submit_job
        with patch("routers.processing_api.validate_file_path", return_value=audio_file):
            response = client.post(
                "/api/processing/process",
                json={"input_path": str(audio_file), "settings": {"mode": "adaptive"}},
            )

        assert response.status_code == 503
        assert "queue" in response.json()["detail"].lower()

    def test_process_happy_path_returns_200_with_job_id(self, client, mock_engine, tmp_path):
        """POST /api/processing/process happy path returns 200 with job_id (fixes #2745)"""
        audio_file = tmp_path / "song.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)
        mock_engine.create_job.return_value = mock_engine.get_job.return_value

        with patch("routers.processing_api.validate_file_path", return_value=audio_file):
            response = client.post(
                "/api/processing/process",
                json={"input_path": str(audio_file), "settings": {"mode": "adaptive"}},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-123"
        assert data["status"] == "queued"
        assert "message" in data
        mock_engine.create_job.assert_called_once()
        mock_engine.submit_job.assert_called_once()

    def test_process_with_reference_path_triggers_matchering(self, client, mock_engine, tmp_path):
        """POST /api/processing/process with reference_path uses reference mode (fixes #2745)"""
        audio_file = tmp_path / "song.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)
        ref_file = tmp_path / "reference.wav"
        ref_file.write_bytes(b"RIFF" + b"\x00" * 40)
        mock_engine.create_job.return_value = mock_engine.get_job.return_value

        def fake_validate(path, context=None):
            # The real validate_file_path takes a keyword `context` for its
            # error messages; the stub went stale when that was added and the
            # test has been erroring on the mismatch rather than exercising
            # the reference path.
            return Path(path)

        with patch("routers.processing_api.validate_file_path", side_effect=fake_validate):
            response = client.post(
                "/api/processing/process",
                json={
                    "input_path": str(audio_file),
                    "reference_path": str(ref_file),
                    "settings": {"mode": "reference"},
                },
            )

        assert response.status_code == 200
        # Verify create_job was called with the reference path
        call_kwargs = mock_engine.create_job.call_args
        assert call_kwargs[1]["reference_path"] == str(ref_file)
        assert call_kwargs[1]["mode"] == "reference"

    def test_process_accepts_snake_case_level_matching(self, client, mock_engine, tmp_path):
        """POST /api/processing/process accepts level_matching in snake_case (fixes #2748)"""
        audio_file = tmp_path / "song.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)
        mock_engine.create_job.return_value = mock_engine.get_job.return_value

        with patch("routers.processing_api.validate_file_path", return_value=audio_file):
            response = client.post(
                "/api/processing/process",
                json={
                    "input_path": str(audio_file),
                    "settings": {
                        "mode": "adaptive",
                        "level_matching": {"enabled": True, "targetLufs": -14},
                    },
                },
            )

        assert response.status_code == 200
        # Verify the setting was passed through to create_job
        call_kwargs = mock_engine.create_job.call_args[1]
        assert call_kwargs["settings"]["level_matching"] == {"enabled": True, "targetLufs": -14}

    def test_process_accepts_camel_case_level_matching(self, client, mock_engine, tmp_path):
        """POST /api/processing/process still accepts legacy levelMatching (fixes #2748)"""
        audio_file = tmp_path / "song.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)
        mock_engine.create_job.return_value = mock_engine.get_job.return_value

        with patch("routers.processing_api.validate_file_path", return_value=audio_file):
            response = client.post(
                "/api/processing/process",
                json={
                    "input_path": str(audio_file),
                    "settings": {
                        "mode": "adaptive",
                        "levelMatching": {"enabled": True, "targetLufs": -16},
                    },
                },
            )

        assert response.status_code == 200

    def test_upload_and_process_returns_503_when_queue_full(self, client, mock_engine):
        """POST /api/processing/upload-and-process returns 503 when queue is full"""
        import asyncio

        mock_engine.submit_job = AsyncMock(side_effect=asyncio.QueueFull())

        audio_data = b"RIFF" + b"\x00" * 40
        files = {"file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}
        data = {"settings": json.dumps({"mode": "adaptive"})}

        response = client.post(
            "/api/processing/upload-and-process",
            files=files,
            data=data,
        )

        assert response.status_code == 503
        assert "queue" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# ============================================================
# Phase 5C.2: Dual-Mode Backend Testing Patterns
# ============================================================
# Following the same pattern as Phase 5C.1 API tests.

@pytest.mark.phase5c
class TestProcessingAPIDualModeParametrized:
    """Phase 5C.3: Parametrized dual-mode tests for audio processing operations.

    These tests automatically run with both LibraryManager and RepositoryFactory
    via the parametrized mock_data_source fixture.
    """

    def test_processing_tracks_interface(self, mock_data_source):
        """
        Parametrized test: Validate tracks repository for processing operations.

        Audio processing requires track data from both access patterns.
        """
        mode, source = mock_data_source

        assert hasattr(source, 'tracks'), f"{mode} missing tracks repository"
        assert hasattr(source.tracks, 'get_all'), f"{mode}.tracks missing get_all"
        assert hasattr(source.tracks, 'get_by_id'), f"{mode}.tracks missing get_by_id"

    def test_processing_get_all_returns_tuple(self, mock_data_source):
        """
        Parametrized test: Validate tracks.get_all returns (items, total) for both modes.

        Processing requires listing tracks with pagination support.
        """
        mode, source = mock_data_source

        # Create mock tracks for processing
        track1 = Mock()
        track1.id = 1
        track1.filepath = "/path/to/track1.wav"
        track1.title = "Track 1"

        track2 = Mock()
        track2.id = 2
        track2.filepath = "/path/to/track2.wav"
        track2.title = "Track 2"

        test_tracks = [track1, track2]
        source.tracks.get_all = Mock(return_value=(test_tracks, 2))

        # Test with both modes
        tracks, total = source.tracks.get_all(limit=50, offset=0)

        assert len(tracks) == 2, f"{mode}: Expected 2 tracks"
        assert total == 2, f"{mode}: Expected total=2"
        assert tracks[0].filepath == "/path/to/track1.wav", f"{mode}: First track filepath mismatch"
        assert tracks[1].filepath == "/path/to/track2.wav", f"{mode}: Second track filepath mismatch"

    def test_processing_get_by_id_interface(self, mock_data_source):
        """
        Parametrized test: Validate tracks.get_by_id works with both modes.

        Processing needs to retrieve individual track for audio file access.
        """
        mode, source = mock_data_source

        track = Mock()
        track.id = 1
        track.filepath = "/path/to/audio.wav"
        track.title = "Test Track"

        source.tracks.get_by_id = Mock(return_value=track)

        result = source.tracks.get_by_id(1)

        assert result.id == 1, f"{mode}: Track ID mismatch"
        assert result.filepath == "/path/to/audio.wav", f"{mode}: Track filepath mismatch"
        assert result.title == "Test Track", f"{mode}: Track title mismatch"
        source.tracks.get_by_id.assert_called_once_with(1)


# ===========================================================================
# _is_valid_audio_magic unit tests
# ===========================================================================

class TestIsValidAudioMagic:
    """Tests for the magic-byte validation gate."""

    @pytest.mark.parametrize("header,desc", [
        (b"RIFF\x00\x00\x00\x00", "WAV"),
        (b"fLaC\x00\x00\x00\x00", "FLAC"),
        (b"OggS\x00\x00\x00\x00", "OGG"),
        (b"ID3\x00\x00\x00\x00\x00", "MP3 ID3v2"),
        (b"\xff\xfb\x00\x00\x00\x00\x00\x00", "MP3 sync 0xfffb"),
        (b"\x00\x00\x00\x1cftyp", "M4A/MP4"),
        (b"FORM\x00\x00\x00\x00", "AIFF FORM"),
    ])
    def test_accepts_valid_audio_magic(self, header: bytes, desc: str):
        assert _is_valid_audio_magic(header) is True, f"Should accept {desc}"

    def test_rejects_mime_valid_but_magic_invalid(self):
        """Primary defence: file claims audio MIME but has non-audio magic bytes.

        Regression test for issue #3232.
        """
        # PNG header — a file that might be served as audio/mpeg by a
        # misconfigured client but is clearly not audio.
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert _is_valid_audio_magic(png_header) is False

    def test_rejects_pdf_magic(self):
        pdf_header = b"%PDF-1.4" + b"\x00" * 100
        assert _is_valid_audio_magic(pdf_header) is False

    def test_rejects_too_short(self):
        assert _is_valid_audio_magic(b"\xff\xfb") is False

    def test_rejects_empty(self):
        assert _is_valid_audio_magic(b"") is False
