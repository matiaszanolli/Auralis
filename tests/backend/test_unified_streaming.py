"""
Tests for Unified Streaming Router

Tests the unified endpoint that intelligently routes between MSE and MTB.
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Import the module to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'))

from routers.unified_streaming import create_unified_streaming_router


@pytest.fixture
def mock_library_manager():
    """Mock library manager"""
    manager = Mock()

    # Mock track
    mock_track = Mock()
    mock_track.id = 1
    mock_track.filepath = "/fake/path/to/track.mp3"
    mock_track.duration = 238.5
    mock_track.title = "Test Track"
    mock_track.artist = "Test Artist"

    # Mock repository
    mock_repo = Mock()
    mock_repo.get_by_id = Mock(return_value=mock_track)
    manager.tracks = mock_repo

    return manager


@pytest.fixture
def mock_multi_tier_buffer():
    """Mock multi-tier buffer manager"""
    return Mock()


@pytest.fixture
def mock_chunked_processor():
    """Mock chunked processor class"""
    return Mock()


@pytest.fixture
def router(mock_library_manager, mock_multi_tier_buffer, mock_chunked_processor):
    """Create unified streaming router with mocks"""
    router = create_unified_streaming_router(
        get_library_manager=lambda: mock_library_manager,
        get_multi_tier_buffer=lambda: mock_multi_tier_buffer,
        chunked_processor_class=mock_chunked_processor,
        chunk_duration=30.0
    )
    return router


@pytest.fixture
def client(router, mock_library_manager):
    """Create test client with router"""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    # Store mock for access in tests
    app.state.library_manager = mock_library_manager

    return TestClient(app)


class TestUnifiedStreamingMetadata:
    """Tests for metadata endpoint"""

    def test_get_metadata_unenhanced(self, client):
        """Test metadata endpoint in unenhanced mode"""
        response = client.get("/api/audio/stream/1/metadata?enhanced=false")

        assert response.status_code == 200
        data = response.json()

        assert data["track_id"] == 1
        assert data["duration"] == 238.5
        assert data["total_chunks"] == 8  # ceil(238.5 / 30)
        assert data["chunk_duration"] == 30.0
        assert data["format"] == "audio/webm; codecs=opus"
        assert data["enhanced"] is False
        assert data["supports_seeking"] is True

    def test_get_metadata_enhanced(self, client):
        """Test metadata endpoint in enhanced mode"""
        response = client.get(
            "/api/audio/stream/1/metadata?enhanced=true&preset=warm"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["track_id"] == 1
        assert data["format"] == "audio/wav"
        assert data["enhanced"] is True
        assert data["preset"] == "warm"

    def test_get_metadata_track_not_found(self, client):
        """Test metadata endpoint with non-existent track"""
        # Mock returns None
        client.app.state.library_manager.tracks.get_by_id = Mock(return_value=None)

        response = client.get("/api/audio/stream/999/metadata?enhanced=false")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_metadata_default_preset(self, client):
        """Test metadata with default preset when not specified"""
        response = client.get("/api/audio/stream/1/metadata?enhanced=true")

        assert response.status_code == 200
        data = response.json()
        assert data["preset"] == "adaptive"  # Default

    def test_get_metadata_custom_chunk_duration(self):
        """Test metadata with custom chunk duration"""
        # Create router with different chunk duration
        mock_lib = Mock()
        mock_track = Mock()
        mock_track.id = 1
        mock_track.filepath = "/fake/track.mp3"
        mock_track.duration = 120.0
        mock_lib.tracks.get_by_id = Mock(return_value=mock_track)

        router = create_unified_streaming_router(
            get_library_manager=lambda: mock_lib,
            get_multi_tier_buffer=lambda: None,
            chunked_processor_class=Mock(),
            chunk_duration=60.0  # Custom duration
        )

        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/audio/stream/1/metadata?enhanced=false")

        assert response.status_code == 200
        data = response.json()
        assert data["chunk_duration"] == 60.0
        assert data["total_chunks"] == 2  # ceil(120 / 60)


class TestUnifiedStreamingChunks:
    """Tests for chunk delivery endpoint"""

    @patch('routers.unified_streaming.librosa')
    @patch('routers.unified_streaming.get_encoder')
    def test_get_chunk_unenhanced_cache_miss(
        self, mock_get_encoder, mock_librosa, client
    ):
        """Test unenhanced chunk delivery with cache miss"""
        # Mock librosa
        import numpy as np
        mock_audio = np.random.rand(44100, 2)  # 1 second stereo
        mock_librosa.load.return_value = (mock_audio, 44100)

        # Mock encoder
        mock_encoder = Mock()
        mock_encoder.get_cached_path.return_value = None  # Cache miss
        mock_webm_path = Path("/tmp/test.webm")
        mock_encoder.encode_chunk = AsyncMock(return_value=mock_webm_path)
        mock_get_encoder.return_value = mock_encoder

        # Mock file opening
        with patch('builtins.open', create=True) as mock_open:
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=None)
            mock_file.read = Mock(return_value=b"webm_data")
            mock_open.return_value = mock_file

            response = client.get(
                "/api/audio/stream/1/chunk/0?enhanced=false"
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/webm; codecs=opus"
        assert response.headers["X-Cache"] == "MISS"

    @patch('routers.unified_streaming.get_encoder')
    def test_get_chunk_unenhanced_cache_hit(self, mock_get_encoder, client):
        """Test unenhanced chunk delivery with cache hit"""
        # Mock encoder with cache hit
        mock_encoder = Mock()
        mock_webm_path = Path("/tmp/cached.webm")
        mock_encoder.get_cached_path.return_value = mock_webm_path
        mock_get_encoder.return_value = mock_encoder

        # Mock file opening
        with patch('builtins.open', create=True) as mock_open:
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=None)
            mock_file.read = Mock(return_value=b"cached_webm_data")
            mock_open.return_value = mock_file

            response = client.get(
                "/api/audio/stream/1/chunk/0?enhanced=false"
            )

        assert response.status_code == 200
        assert response.headers["X-Cache"] == "HIT"

    def test_get_chunk_enhanced(self, client):
        """Test enhanced chunk delivery (placeholder for MTB integration)"""
        # Currently returns placeholder response
        response = client.get(
            "/api/audio/stream/1/chunk/0?enhanced=true&preset=warm"
        )

        # Should eventually work, but currently may fail
        # This test documents expected behavior
        assert response.status_code in [200, 501]  # 501 = Not Implemented yet

    def test_get_chunk_invalid_track(self, client):
        """Test chunk delivery with invalid track ID"""
        client.app.state.library_manager.tracks.get_by_id = Mock(return_value=None)

        response = client.get(
            "/api/audio/stream/999/chunk/0?enhanced=false"
        )

        assert response.status_code == 404

    def test_get_chunk_invalid_chunk_index(self, client):
        """Test chunk delivery with out-of-bounds chunk index"""
        # Track has 8 chunks (238.5s / 30s)
        response = client.get(
            "/api/audio/stream/1/chunk/999?enhanced=false"
        )

        # Should handle gracefully
        assert response.status_code in [400, 404]

    @patch('routers.unified_streaming.librosa')
    def test_get_chunk_librosa_error(self, mock_librosa, client):
        """Test chunk delivery with librosa error"""
        mock_librosa.load.side_effect = Exception("Failed to load audio")

        response = client.get(
            "/api/audio/stream/1/chunk/0?enhanced=false"
        )

        assert response.status_code == 500


class TestUnifiedStreamingCache:
    """Tests for cache management endpoints"""

    @patch('routers.unified_streaming.get_encoder')
    def test_get_cache_stats(self, mock_get_encoder, client):
        """Test cache statistics endpoint"""
        # Mock encoder stats
        mock_encoder = Mock()
        mock_encoder.get_cache_size.return_value = (10, 5.5)  # 10 files, 5.5 MB
        mock_get_encoder.return_value = mock_encoder

        response = client.get("/api/audio/stream/cache/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["webm_cache"]["file_count"] == 10
        assert data["webm_cache"]["size_mb"] == 5.5

    @patch('routers.unified_streaming.get_encoder')
    def test_clear_cache(self, mock_get_encoder, client):
        """Test cache clearing endpoint"""
        mock_encoder = Mock()
        mock_encoder.clear_cache.return_value = None
        mock_get_encoder.return_value = mock_encoder

        response = client.delete("/api/audio/stream/cache/clear")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        mock_encoder.clear_cache.assert_called_once()


@pytest.mark.integration
class TestUnifiedStreamingIntegration:
    """Integration tests with real components"""

    def test_full_flow_unenhanced(self, tmp_path):
        """Test complete flow: metadata → chunk delivery"""
        # This would test with real library, real audio files
        # Requires test fixtures to be set up
        pytest.skip("Requires test audio files and library setup")

    def test_mode_switching(self, tmp_path):
        """Test switching between enhanced/unenhanced for same track"""
        pytest.skip("Requires full integration environment")


class TestUnifiedStreamingEdgeCases:
    """Tests for edge cases and error conditions"""

    def test_concurrent_chunk_requests(self, client):
        """Test handling of concurrent chunk requests"""
        # Test that concurrent requests don't cause race conditions
        pytest.skip("Requires async test client")

    def test_large_file_handling(self, client):
        """Test handling of very large audio files"""
        # Mock track with long duration
        mock_track = Mock()
        mock_track.id = 1
        mock_track.filepath = "/fake/large.mp3"
        mock_track.duration = 36000.0  # 10 hours
        client.app.state.library_manager.tracks.get_by_id = Mock(return_value=mock_track)

        response = client.get("/api/audio/stream/1/metadata?enhanced=false")

        assert response.status_code == 200
        data = response.json()
        assert data["total_chunks"] == 1200  # ceil(36000 / 30)

    def test_zero_duration_track(self, client):
        """Test handling of track with zero duration"""
        mock_track = Mock()
        mock_track.id = 1
        mock_track.filepath = "/fake/empty.mp3"
        mock_track.duration = 0.0
        client.app.state.library_manager.tracks.get_by_id = Mock(return_value=mock_track)

        response = client.get("/api/audio/stream/1/metadata?enhanced=false")

        # Should handle gracefully
        assert response.status_code in [200, 400]

    @patch('routers.unified_streaming.os.path.exists')
    def test_missing_audio_file(self, mock_exists, client):
        """Test handling when audio file doesn't exist"""
        mock_exists.return_value = False

        response = client.get("/api/audio/stream/1/metadata?enhanced=false")

        # Should detect missing file
        assert response.status_code in [404, 500]
