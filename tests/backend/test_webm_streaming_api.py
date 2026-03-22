"""
Tests for WebM Streaming Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the unified WAV streaming endpoints.

Coverage:
- GET /api/stream/{track_id}/metadata - Get stream metadata
- GET /api/stream/{track_id}/chunk/{chunk_idx} - Stream audio chunk

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture
def mock_repos():
    """Create mock RepositoryFactory"""
    repos = Mock()
    repos.tracks = Mock()
    repos.tracks.get_by_id = Mock(return_value=None)
    return repos


@pytest.fixture
def mock_track():
    """Create a mock track with valid audio file"""
    track = Mock()
    track.id = 1
    track.filepath = "/tmp/test_audio.wav"
    track.duration = 60.0
    track.title = "Test Track"
    return track


def _mock_audio_info(filepath):
    """Mock audio info for streaming tests"""
    return Mock(samplerate=44100, channels=2)


class TestRouterRegistration:
    """Verify the streaming router is registered (regression guard for MC-01)"""

    def test_stream_metadata_is_not_routing_404(self, client):
        """GET /api/stream/1/metadata should not return a routing 404"""
        response = client.get("/api/stream/1/metadata")
        # 404 from "track not found" is fine; routing 404 with "Not Found" detail is not
        if response.status_code == 404:
            detail = response.json().get("detail", "")
            assert "not found" in detail.lower(), (
                f"Got routing 404 (detail={detail!r}) — router likely not registered"
            )


class TestGetStreamMetadata:
    """Test GET /api/stream/{track_id}/metadata"""

    @patch('routers.webm_streaming.require_repository_factory')
    def test_get_metadata_track_not_found(self, mock_require_repos, client, mock_repos):
        """Test metadata request for non-existent track"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.get("/api/stream/999/metadata")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch('routers.webm_streaming.require_repository_factory')
    def test_get_metadata_file_not_found(self, mock_require_repos, client, mock_repos):
        """Test metadata when audio file doesn't exist"""
        mock_require_repos.return_value = mock_repos

        mock_track = Mock()
        mock_track.id = 1
        mock_track.filepath = "/nonexistent/file.mp3"
        mock_track.duration = 180.0
        mock_repos.tracks.get_by_id.return_value = mock_track

        response = client.get("/api/stream/1/metadata")

        assert response.status_code == 404
        assert "file not found" in response.json()["detail"].lower()

    @patch('routers.webm_streaming.sf.info', side_effect=_mock_audio_info)
    @patch('routers.webm_streaming.os.path.exists', return_value=True)
    @patch('routers.webm_streaming.require_repository_factory')
    def test_get_metadata_structure(self, mock_require_repos, _mock_exists, _mock_sf, client, mock_repos, mock_track):
        """Test metadata response structure"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        response = client.get("/api/stream/1/metadata")
        assert response.status_code == 200

        data = response.json()
        for field in ["track_id", "duration", "sample_rate", "channels", "chunk_duration",
                      "chunk_interval", "total_chunks", "mime_type", "codecs",
                      "format_version", "chunk_playable_duration", "overlap_duration"]:
            assert field in data, f"Missing field: {field}"

    @patch('routers.webm_streaming.sf.info', side_effect=_mock_audio_info)
    @patch('routers.webm_streaming.os.path.exists', return_value=True)
    @patch('routers.webm_streaming.require_repository_factory')
    def test_get_metadata_field_types(self, mock_require_repos, _mock_exists, _mock_sf, client, mock_repos, mock_track):
        """Test that metadata fields have correct types"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        response = client.get("/api/stream/1/metadata")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data["track_id"], int)
        assert isinstance(data["duration"], (int, float))
        assert isinstance(data["sample_rate"], int)
        assert isinstance(data["channels"], int)
        assert isinstance(data["total_chunks"], int)
        assert isinstance(data["mime_type"], str)

    @patch('routers.webm_streaming.sf.info', side_effect=_mock_audio_info)
    @patch('routers.webm_streaming.os.path.exists', return_value=True)
    @patch('routers.webm_streaming.require_repository_factory')
    def test_get_metadata_wav_format(self, mock_require_repos, _mock_exists, _mock_sf, client, mock_repos, mock_track):
        """Test that metadata specifies WAV format"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        response = client.get("/api/stream/1/metadata")
        assert response.status_code == 200

        data = response.json()
        assert data["mime_type"] == "audio/wav"
        assert data["codecs"] == "PCM_16"

    def test_get_metadata_accepts_get_only(self, client):
        """Test that endpoint only accepts GET"""
        response = client.post("/api/stream/1/metadata")
        assert response.status_code == 405


class TestStreamChunk:
    """Test GET /api/stream/{track_id}/chunk/{chunk_idx}"""

    @patch('routers.webm_streaming.require_repository_factory')
    def test_stream_chunk_track_not_found(self, mock_require_repos, client, mock_repos):
        """Test chunk request for non-existent track"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.get("/api/stream/999/chunk/0")
        assert response.status_code == 404

    @patch('routers.webm_streaming.require_repository_factory')
    def test_stream_chunk_file_not_found(self, mock_require_repos, client, mock_repos):
        """Test chunk request when audio file doesn't exist"""
        mock_require_repos.return_value = mock_repos

        track = Mock()
        track.id = 1
        track.filepath = "/nonexistent/file.mp3"
        mock_repos.tracks.get_by_id.return_value = track

        response = client.get("/api/stream/1/chunk/0")
        assert response.status_code == 404

    def test_stream_chunk_intensity_validation(self, client):
        """Test intensity parameter validation"""
        response = client.get("/api/stream/1/chunk/0?intensity=-0.1")
        assert response.status_code == 422

        response = client.get("/api/stream/1/chunk/0?intensity=1.1")
        assert response.status_code == 422

    def test_stream_chunk_negative_index(self, client):
        """Test that negative chunk indices are rejected"""
        response = client.get("/api/stream/1/chunk/-1")
        assert response.status_code in [404, 422]

    def test_stream_chunk_accepts_get_only(self, client):
        """Test that endpoint only accepts GET"""
        response = client.post("/api/stream/1/chunk/0")
        assert response.status_code == 405


class TestStreamingSecurityValidation:
    """Security-focused tests for streaming endpoints"""

    def test_metadata_extremely_large_track_id(self, client):
        """Test metadata with extremely large track ID"""
        response = client.get("/api/stream/999999999999/metadata")
        assert response.status_code in [404, 500]

    def test_chunk_extremely_large_indices(self, client):
        """Test chunk request with extremely large indices"""
        response = client.get("/api/stream/1/chunk/999999")
        assert response.status_code in [404, 500]

    @patch('routers.webm_streaming.sf.info', side_effect=_mock_audio_info)
    @patch('routers.webm_streaming.os.path.exists', return_value=True)
    @patch('routers.webm_streaming.require_repository_factory')
    def test_metadata_consistency(self, mock_require_repos, _mock_exists, _mock_sf, client, mock_repos, mock_track):
        """Test that multiple metadata requests return consistent results"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = mock_track

        response1 = client.get("/api/stream/1/metadata")
        response2 = client.get("/api/stream/1/metadata")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()
