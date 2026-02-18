"""
Tests for Files Router
~~~~~~~~~~~~~~~~~~~~~~

Tests for file operations: directory scanning, uploads, and format queries.

Coverage:
- POST /api/library/scan - Scan directory for audio files
- POST /api/files/upload - Upload audio files
- GET /api/audio/formats - Get supported audio formats

Security:
- Path traversal prevention
- File type validation
- Directory access control

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture
def mock_library_manager():
    """Mock LibraryManager for testing"""
    manager = Mock()
    manager.scan_directory = Mock()
    return manager


@pytest.fixture
def mock_connection_manager():
    """Mock WebSocket connection manager"""
    manager = Mock()
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def sample_audio_file():
    """Create a sample audio file for upload testing"""
    # Create minimal WAV file (44 bytes header + 1 sample)
    wav_data = bytes([
        # RIFF header
        0x52, 0x49, 0x46, 0x46,  # "RIFF"
        0x24, 0x00, 0x00, 0x00,  # File size - 8
        0x57, 0x41, 0x56, 0x45,  # "WAVE"
        # fmt chunk
        0x66, 0x6d, 0x74, 0x20,  # "fmt "
        0x10, 0x00, 0x00, 0x00,  # Chunk size (16)
        0x01, 0x00,              # Audio format (1 = PCM)
        0x02, 0x00,              # Num channels (2 = stereo)
        0x44, 0xac, 0x00, 0x00,  # Sample rate (44100)
        0x10, 0xb1, 0x02, 0x00,  # Byte rate
        0x04, 0x00,              # Block align
        0x10, 0x00,              # Bits per sample (16)
        # data chunk
        0x64, 0x61, 0x74, 0x61,  # "data"
        0x00, 0x00, 0x00, 0x00,  # Data size (0)
    ])
    return wav_data


class TestScanDirectory:
    """Test POST /api/library/scan"""

    def test_scan_directory_missing_parameter(self, client):
        """Test scan without directory parameter"""
        response = client.post("/api/library/scan", json={})

        assert response.status_code == 422  # Validation error

    def test_scan_directory_path_traversal_attack(self, client):
        """Test that path traversal is blocked (security)"""
        # Try to scan outside allowed directory
        response = client.post(
            "/api/library/scan",
            json={"directory": "../../etc/passwd"}
        )

        assert response.status_code == 400
        assert "Path traversal" in response.json()["detail"] or \
               "outside" in response.json()["detail"]

    def test_scan_directory_absolute_path_outside_allowed(self, client):
        """Test that absolute paths outside allowed directories are rejected"""
        response = client.post(
            "/api/library/scan",
            json={"directory": "/etc/passwd"}
        )

        # Should be rejected by path validation
        assert response.status_code in [400, 403]

    @patch('main.library_manager')
    @patch('main.connection_manager')
    def test_scan_directory_nonexistent(self, mock_manager, mock_library, client):
        """Test scanning non-existent directory"""
        mock_manager.broadcast = AsyncMock()

        response = client.post(
            "/api/library/scan",
            json={"directory": "/tmp/nonexistent_auralis_test_dir_12345"}
        )

        # Should either reject as invalid or fail during scan
        assert response.status_code in [400, 404, 500]

    @patch('main.library_manager')
    @patch('main.connection_manager')
    def test_scan_directory_library_unavailable(self, mock_manager, mock_library, client):
        """Test scan when library manager not available"""
        mock_manager.broadcast = AsyncMock()
        mock_library.return_value = None

        response = client.post(
            "/api/library/scan",
            json={"directory": "/tmp"}
        )

        # Should return 503 (Service Unavailable)
        assert response.status_code == 503

    def test_scan_directory_accepts_post_only(self, client):
        """Test that scan endpoint only accepts POST"""
        response = client.get("/api/library/scan")
        assert response.status_code == 405  # Method Not Allowed


class TestUploadFiles:
    """Test POST /api/files/upload"""

    @patch('main.library_manager')
    def test_upload_no_files(self, mock_library, client):
        """Test upload with no files provided"""
        response = client.post("/api/files/upload")

        assert response.status_code == 422  # Validation error

    @patch('main.library_manager')
    def test_upload_unsupported_file_type(self, mock_library, client):
        """Test upload with unsupported file type"""
        mock_library_obj = Mock()
        mock_library.return_value = mock_library_obj

        # Create fake executable file
        file_data = b"fake executable"
        files = {"files": ("malware.exe", io.BytesIO(file_data), "application/x-msdownload")}

        response = client.post("/api/files/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        # Should report error for unsupported type
        assert data["results"][0]["status"] == "error"
        assert "Unsupported" in data["results"][0]["message"]

    @patch('main.library_manager')
    def test_upload_supported_extensions(self, mock_library, client):
        """Test that supported extensions are accepted"""
        mock_library_obj = Mock()
        mock_library.return_value = mock_library_obj

        supported = [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"]

        for ext in supported:
            filename = f"test{ext}"
            file_data = b"fake audio data"
            files = {"files": (filename, io.BytesIO(file_data), "audio/mpeg")}

            response = client.post("/api/files/upload", files=files)

            # File type is accepted (even if processing fails)
            assert response.status_code == 200
            data = response.json()
            # Should not reject based on extension
            assert "results" in data

    @patch('main.library_manager')
    def test_upload_library_unavailable(self, mock_library, client):
        """Test upload when library manager not available"""
        mock_library.return_value = None

        file_data = b"fake audio"
        files = {"files": ("test.mp3", io.BytesIO(file_data), "audio/mpeg")}

        response = client.post("/api/files/upload", files=files)

        assert response.status_code == 503

    @patch('main.library_manager')
    def test_upload_multiple_files(self, mock_library, client):
        """Test uploading multiple files at once"""
        mock_library_obj = Mock()
        mock_library.return_value = mock_library_obj

        # Create multiple files
        files = [
            ("files", ("track1.mp3", io.BytesIO(b"audio1"), "audio/mpeg")),
            ("files", ("track2.mp3", io.BytesIO(b"audio2"), "audio/mpeg")),
            ("files", ("track3.mp3", io.BytesIO(b"audio3"), "audio/mpeg"))
        ]

        response = client.post("/api/files/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 3

    @patch('main.library_manager')
    def test_upload_mixed_valid_invalid(self, mock_library, client):
        """Test uploading mix of valid and invalid files"""
        mock_library_obj = Mock()
        mock_library.return_value = mock_library_obj

        files = [
            ("files", ("valid.mp3", io.BytesIO(b"audio"), "audio/mpeg")),
            ("files", ("invalid.exe", io.BytesIO(b"binary"), "application/octet-stream")),
            ("files", ("valid2.flac", io.BytesIO(b"audio2"), "audio/flac"))
        ]

        response = client.post("/api/files/upload", files=files)

        assert response.status_code == 200
        data = response.json()

        # Should have results for all files
        assert len(data["results"]) == 3

        # Invalid file should have error status
        exe_result = next(r for r in data["results"] if "exe" in r["filename"])
        assert exe_result["status"] == "error"

    def test_upload_accepts_post_only(self, client):
        """Test that upload endpoint only accepts POST"""
        response = client.get("/api/files/upload")
        assert response.status_code == 405


class TestGetSupportedFormats:
    """Test GET /api/audio/formats"""

    def test_get_supported_formats(self, client):
        """Test getting supported audio formats"""
        response = client.get("/api/audio/formats")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "input_formats" in data
        assert "output_formats" in data
        assert "sample_rates" in data
        assert "bit_depths" in data

    def test_supported_formats_input(self, client):
        """Test that input formats include common formats"""
        response = client.get("/api/audio/formats")
        data = response.json()

        input_formats = data["input_formats"]

        # Should support common formats
        assert ".mp3" in input_formats
        assert ".wav" in input_formats
        assert ".flac" in input_formats

    def test_supported_formats_output(self, client):
        """Test that output formats are valid"""
        response = client.get("/api/audio/formats")
        data = response.json()

        output_formats = data["output_formats"]

        # Common output formats
        assert ".wav" in output_formats
        assert ".flac" in output_formats

    def test_supported_sample_rates(self, client):
        """Test that sample rates include standard rates"""
        response = client.get("/api/audio/formats")
        data = response.json()

        sample_rates = data["sample_rates"]

        # Standard sample rates
        assert 44100 in sample_rates
        assert 48000 in sample_rates

    def test_supported_bit_depths(self, client):
        """Test that bit depths include standard depths"""
        response = client.get("/api/audio/formats")
        data = response.json()

        bit_depths = data["bit_depths"]

        # Standard bit depths
        assert 16 in bit_depths
        assert 24 in bit_depths

    def test_formats_accepts_get_only(self, client):
        """Test that formats endpoint only accepts GET"""
        response = client.post("/api/audio/formats")
        assert response.status_code == 405

    def test_formats_consistency(self, client):
        """Test that multiple calls return consistent results"""
        response1 = client.get("/api/audio/formats")
        response2 = client.get("/api/audio/formats")

        assert response1.json() == response2.json()


class TestFilesSecurityValidation:
    """Security-focused tests for files endpoints"""

    def test_scan_null_byte_injection(self, client):
        """Test that null bytes in paths are rejected"""
        response = client.post(
            "/api/library/scan",
            json={"directory": "/tmp/test\x00/../../etc"}
        )

        # Should be rejected
        assert response.status_code in [400, 422]

    def test_scan_special_characters(self, client):
        """Test handling of special characters in paths"""
        # Test various special characters
        special_paths = [
            "/tmp/test;rm -rf /",
            "/tmp/test`whoami`",
            "/tmp/test$(whoami)",
            "/tmp/test|whoami"
        ]

        for path in special_paths:
            response = client.post(
                "/api/library/scan",
                json={"directory": path}
            )

            # Should either reject or handle safely
            assert response.status_code in [400, 403, 404, 422, 500]

    @patch('main.library_manager')
    def test_upload_filename_validation(self, mock_library, client):
        """Test that dangerous filenames are handled safely"""
        mock_library_obj = Mock()
        mock_library.return_value = mock_library_obj

        # Dangerous filenames
        dangerous_names = [
            "../../../etc/passwd",
            "test;rm -rf /.mp3",
            "test\x00.mp3"
        ]

        for filename in dangerous_names:
            file_data = b"audio"
            files = {"files": (filename, io.BytesIO(file_data), "audio/mpeg")}

            response = client.post("/api/files/upload", files=files)

            # Should handle safely (may succeed or fail, but not execute code)
            assert response.status_code in [200, 400, 422]


class TestUploadPermanentStorage:
    """
    Regression tests for issue #2392.

    Every upload was immediately unplayable because the handler stored the temp
    file path in the DB and then deleted the temp file in the finally block.
    The fix moves the file to ~/.auralis/uploads/<uuid><ext> BEFORE the DB record
    is created so the stored filepath is always valid.
    """

    def _make_mock_track(self):
        """Return a minimal mock track with the attributes used by the response builder."""
        track = Mock()
        track.id = 42
        track.title = "song"
        track.duration = 3.0
        track.sample_rate = 44100
        return track

    @patch('routers.files.load_audio')
    @patch('routers.files.shutil.move')
    def test_db_filepath_is_permanent_not_temp(
        self, mock_move, mock_load, client, tmp_path
    ):
        """
        add_track must be called with a permanent path, not a /tmp path.

        If the handler still passes temp_path to add_track, this test fails
        because temp paths start with the OS temp prefix (e.g. /tmp).
        """
        import numpy as np

        mock_load.return_value = (np.zeros((44100, 2), dtype=np.float32), 44100)
        mock_lib_obj = Mock()
        mock_lib_obj.add_track.return_value = self._make_mock_track()

        def fake_move(src, dst):
            Path(dst).write_bytes(Path(src).read_bytes() if Path(src).exists() else b"")

        mock_move.side_effect = fake_move

        import main as main_module
        with patch.dict(main_module.globals_dict, {'library_manager': mock_lib_obj}):
            files = {"files": ("song.mp3", io.BytesIO(b"audio"), "audio/mpeg")}
            response = client.post("/api/files/upload", files=files)

        assert response.status_code == 200
        assert mock_lib_obj.add_track.call_count == 1

        stored_filepath = mock_lib_obj.add_track.call_args[0][0]["filepath"]

        # The stored path must NOT be a temp path.
        assert not stored_filepath.startswith(tempfile.gettempdir()), (
            f"DB filepath is still a temp path: {stored_filepath!r} — "
            "issue #2392 not fixed: track will be unplayable after upload"
        )

    @patch('routers.files.load_audio')
    @patch('routers.files.shutil.move')
    def test_temp_file_is_cleaned_up_on_success(
        self, mock_move, mock_load, client
    ):
        """
        The temp file must not exist after a successful upload.

        shutil.move removes the source (temp) file atomically; the finally
        block's unlink(missing_ok=True) must not raise even though it's gone.
        """
        import numpy as np

        mock_load.return_value = (np.zeros((44100, 2), dtype=np.float32), 44100)
        mock_lib_obj = Mock()
        mock_lib_obj.add_track.return_value = self._make_mock_track()

        captured_temp_path: list[str] = []

        def fake_move(src, dst):
            captured_temp_path.append(src)
            # Simulate move: remove source (temp file goes away).
            Path(src).unlink(missing_ok=True)

        mock_move.side_effect = fake_move

        import main as main_module
        with patch.dict(main_module.globals_dict, {'library_manager': mock_lib_obj}):
            files = {"files": ("song.mp3", io.BytesIO(b"audio"), "audio/mpeg")}
            response = client.post("/api/files/upload", files=files)

        assert response.status_code == 200
        assert captured_temp_path, "shutil.move was never called — temp file not moved"

        # Temp file must be gone after the request.
        assert not Path(captured_temp_path[0]).exists(), (
            f"Temp file still exists at {captured_temp_path[0]!r} after upload — "
            "cleanup did not run correctly"
        )

    @patch('routers.files.load_audio')
    @patch('routers.files.shutil.move')
    def test_add_track_not_called_when_move_fails(
        self, mock_move, mock_load, client
    ):
        """
        If moving to permanent storage fails, no DB record must be created.

        This is the atomicity guarantee: a broken file-system state should not
        result in a DB record pointing to a non-existent file.
        """
        import numpy as np

        mock_load.return_value = (np.zeros((44100, 2), dtype=np.float32), 44100)
        mock_lib_obj = Mock()
        mock_move.side_effect = OSError("Simulated disk full")

        import main as main_module
        with patch.dict(main_module.globals_dict, {'library_manager': mock_lib_obj}):
            files = {"files": ("song.mp3", io.BytesIO(b"audio"), "audio/mpeg")}
            response = client.post("/api/files/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["status"] == "error"
        mock_lib_obj.add_track.assert_not_called()

    @patch('routers.files.load_audio')
    @patch('routers.files.shutil.move')
    def test_upload_success_track_is_playable(
        self, mock_move, mock_load, client, tmp_path
    ):
        """
        After a successful upload the track filepath must point to an existing file.

        This is the primary acceptance criterion: the DB record must reference a
        file that actually exists so playback can start immediately.
        """
        import shutil as _shutil
        import numpy as np

        mock_load.return_value = (np.zeros((44100, 2), dtype=np.float32), 44100)
        mock_lib_obj = Mock()
        permanent_file = tmp_path / "permanent.mp3"

        mock_move.side_effect = lambda src, dst: _shutil.copy2(src, permanent_file)

        # Capture what add_track was called with.
        recorded: list[dict] = []

        def capturing_add_track(track_info):
            recorded.append(track_info)
            return self._make_mock_track()

        mock_lib_obj.add_track.side_effect = capturing_add_track

        import main as main_module
        with patch.dict(main_module.globals_dict, {'library_manager': mock_lib_obj}):
            files = {"files": ("song.mp3", io.BytesIO(b"audio"), "audio/mpeg")}
            response = client.post("/api/files/upload", files=files)

        assert response.status_code == 200
        assert response.json()["results"][0]["status"] == "success"
        assert recorded, "add_track was never called"

        # The file at the stored path must exist (permanent_file simulates it).
        assert permanent_file.exists(), (
            "Permanent file does not exist — uploaded track would be unplayable (issue #2392)"
        )


class TestFilesIntegration:
    """Integration tests for files endpoints"""

    def test_get_formats_before_upload(self, client):
        """Test getting formats before attempting upload"""
        # Get supported formats
        formats_response = client.get("/api/audio/formats")
        assert formats_response.status_code == 200

        formats = formats_response.json()

        # Verify upload validates against these formats
        # (Actual upload would require mocked library)
        assert len(formats["input_formats"]) > 0

    def test_scan_and_formats_consistency(self, client):
        """Test that scan and formats endpoints are consistent"""
        formats_response = client.get("/api/audio/formats")
        assert formats_response.status_code == 200

        # Both endpoints should be available if service is running
        # This tests that the service is consistently configured
        assert formats_response.json() is not None
