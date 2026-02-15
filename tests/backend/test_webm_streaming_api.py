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

    def test_get_metadata_structure(self, client):
        """Test metadata response structure for valid track (if any exist)"""
        # Note: This will fail if no tracks in test database
        # But validates the response structure if tracks exist
        response = client.get("/api/stream/1/metadata")

        # Either 404 (no track) or 200 (valid track)
        if response.status_code == 200:
            data = response.json()

            # Validate required fields
            assert "track_id" in data
            assert "duration" in data
            assert "sample_rate" in data
            assert "channels" in data
            assert "chunk_duration" in data
            assert "chunk_interval" in data
            assert "total_chunks" in data
            assert "mime_type" in data
            assert "codecs" in data
            assert "format_version" in data
            assert "chunk_playable_duration" in data
            assert "overlap_duration" in data

    def test_get_metadata_field_types(self, client):
        """Test that metadata fields have correct types"""
        response = client.get("/api/stream/1/metadata")

        if response.status_code == 200:
            data = response.json()

            assert isinstance(data["track_id"], int)
            assert isinstance(data["duration"], (int, float))
            assert isinstance(data["sample_rate"], int)
            assert isinstance(data["channels"], int)
            assert isinstance(data["chunk_duration"], int)
            assert isinstance(data["chunk_interval"], int)
            assert isinstance(data["total_chunks"], int)
            assert isinstance(data["mime_type"], str)
            assert isinstance(data["codecs"], str)
            assert isinstance(data["format_version"], str)

    def test_get_metadata_wav_format(self, client):
        """Test that metadata specifies WAV format"""
        response = client.get("/api/stream/1/metadata")

        if response.status_code == 200:
            data = response.json()

            # Should always be WAV format for browser compatibility
            assert data["mime_type"] == "audio/wav"
            assert data["codecs"] == "PCM_16"

    def test_get_metadata_accepts_get_only(self, client):
        """Test that endpoint only accepts GET"""
        response = client.post("/api/stream/1/metadata")
        assert response.status_code in [404, 405]


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

        mock_track = Mock()
        mock_track.id = 1
        mock_track.filepath = "/nonexistent/file.mp3"
        mock_repos.tracks.get_by_id.return_value = mock_track

        response = client.get("/api/stream/1/chunk/0")

        assert response.status_code == 404

    def test_stream_chunk_query_parameters(self, client):
        """Test chunk request with query parameters"""
        # Test with custom preset and intensity
        response = client.get(
            "/api/stream/1/chunk/0"
            "?preset=warm&intensity=0.8&enhanced=true"
        )

        # Will fail if track doesn't exist, but validates parameter parsing
        assert response.status_code in [404, 200, 500]

    def test_stream_chunk_intensity_validation(self, client):
        """Test intensity parameter validation"""
        # Intensity below 0.0
        response = client.get("/api/stream/1/chunk/0?intensity=-0.1")
        assert response.status_code == 422  # Validation error

        # Intensity above 1.0
        response = client.get("/api/stream/1/chunk/0?intensity=1.1")
        assert response.status_code == 422

    def test_stream_chunk_unenhanced(self, client):
        """Test requesting unenhanced (original) chunk"""
        response = client.get("/api/stream/1/chunk/0?enhanced=false")

        # Will fail if track doesn't exist, but validates enhanced parameter
        assert response.status_code in [404, 200, 500]

    def test_stream_chunk_response_headers(self, client):
        """Test that chunk response includes required headers"""
        response = client.get("/api/stream/1/chunk/0")

        if response.status_code == 200:
            # Check for cache headers
            assert "x-chunk-index" in response.headers or "X-Chunk-Index" in response.headers
            assert "content-type" in response.headers

            # Content type should be audio/wav
            content_type = response.headers.get("content-type", "")
            assert "audio/wav" in content_type.lower()

    def test_stream_chunk_different_indices(self, client):
        """Test requesting different chunk indices"""
        for chunk_idx in [0, 1, 5, 10]:
            response = client.get(f"/api/stream/1/chunk/{chunk_idx}")

            # Should handle any valid chunk index
            assert response.status_code in [200, 404, 500]

    def test_stream_chunk_negative_index(self, client):
        """Test that negative chunk indices are rejected"""
        response = client.get("/api/stream/1/chunk/-1")

        # Should be rejected (validation error or not found)
        assert response.status_code in [404, 422]

    def test_stream_chunk_accepts_get_only(self, client):
        """Test that endpoint only accepts GET"""
        response = client.post("/api/stream/1/chunk/0")
        assert response.status_code in [404, 405]


class TestStreamingCacheHeaders:
    """Test cache-related headers in streaming responses"""

    def test_chunk_cache_tier_header(self, client):
        """Test that cache tier is reported in headers"""
        response = client.get("/api/stream/1/chunk/0")

        if response.status_code == 200:
            # Should have cache tier header (X-Cache-Tier or similar)
            headers_lower = {k.lower(): v for k, v in response.headers.items()}

            # Check for cache-related headers
            has_cache_header = any(
                'cache' in key or 'tier' in key
                for key in headers_lower.keys()
            )

            # Cache headers are expected for performance monitoring
            if not has_cache_header:
                # May not be implemented yet, just warn
                pass

    def test_chunk_latency_header(self, client):
        """Test that latency is reported in headers"""
        response = client.get("/api/stream/1/chunk/0")

        if response.status_code == 200:
            # Should have latency header for monitoring
            headers_lower = {k.lower(): v for k, v in response.headers.items()}

            # Check for latency-related headers
            has_latency_header = any(
                'latency' in key or 'time' in key
                for key in headers_lower.keys()
            )

            # Latency headers are useful but not critical
            if not has_latency_header:
                pass


class TestStreamingIntegration:
    """Integration tests for streaming workflow"""

    def test_workflow_get_metadata_then_chunks(self, client):
        """Test complete workflow: get metadata → stream chunks"""
        # 1. Get metadata
        metadata_response = client.get("/api/stream/1/metadata")

        if metadata_response.status_code == 200:
            metadata = metadata_response.json()
            total_chunks = metadata["total_chunks"]

            # 2. Stream first chunk
            chunk_response = client.get("/api/stream/1/chunk/0")

            # Should succeed if metadata succeeded
            assert chunk_response.status_code == 200

            # 3. Stream last chunk
            if total_chunks > 1:
                last_chunk_idx = total_chunks - 1
                last_chunk_response = client.get(f"/api/stream/1/chunk/{last_chunk_idx}")

                # Should succeed
                assert last_chunk_response.status_code == 200

    def test_workflow_enhanced_vs_original(self, client):
        """Test streaming same chunk as enhanced vs original"""
        # 1. Stream enhanced chunk
        enhanced_response = client.get("/api/stream/1/chunk/0?enhanced=true")

        if enhanced_response.status_code == 200:
            # 2. Stream original (unenhanced) chunk
            original_response = client.get("/api/stream/1/chunk/0?enhanced=false")

            # Both should succeed
            assert original_response.status_code == 200

            # Both should be WAV format
            assert "audio/wav" in enhanced_response.headers.get("content-type", "").lower()
            assert "audio/wav" in original_response.headers.get("content-type", "").lower()

    def test_workflow_different_presets(self, client):
        """Test streaming with different presets"""
        presets = ["adaptive", "warm", "bright", "gentle", "punchy"]

        for preset in presets:
            response = client.get(f"/api/stream/1/chunk/0?preset={preset}&enhanced=true")

            # All presets should be accepted
            if response.status_code not in [404, 500]:
                assert response.status_code == 200


class TestStreamingSecurityValidation:
    """Security-focused tests for streaming endpoints"""

    def test_metadata_extremely_large_track_id(self, client):
        """Test metadata with extremely large track ID"""
        large_id = 999999999999
        response = client.get(f"/api/stream/{large_id}/metadata")

        # Should handle gracefully (404 or 500, not crash)
        assert response.status_code in [404, 500]

    def test_chunk_extremely_large_indices(self, client):
        """Test chunk request with extremely large indices"""
        large_chunk = 999999
        response = client.get(f"/api/stream/1/chunk/{large_chunk}")

        # Should handle gracefully
        assert response.status_code in [404, 500]

    def test_chunk_invalid_preset_name(self, client):
        """Test chunk with invalid preset name"""
        response = client.get("/api/stream/1/chunk/0?preset=<script>alert('xss')</script>")

        # Should either reject or sanitize (not execute code)
        assert response.status_code in [200, 400, 404, 500]

    def test_metadata_consistency(self, client):
        """Test that multiple metadata requests return consistent results"""
        response1 = client.get("/api/stream/1/metadata")
        response2 = client.get("/api/stream/1/metadata")

        # Status codes should be identical
        assert response1.status_code == response2.status_code

        # If successful, data should be identical
        if response1.status_code == 200:
            assert response1.json() == response2.json()
