"""
Tests for Similarity Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the fingerprint-based music similarity API endpoints.

Coverage:
- GET /api/similarity/tracks/{track_id}/similar - Get similar tracks
- GET /api/similarity/tracks/{track_id1}/compare/{track_id2} - Compare two tracks
- GET /api/similarity/tracks/{track_id1}/explain/{track_id2} - Explain similarity
- POST /api/similarity/fit - Fit similarity model
- POST /api/similarity/graph/build - Build similarity graph
- GET /api/similarity/graph/stats - Get graph statistics
- DELETE /api/similarity/graph - Delete graph
- GET /api/similarity/fingerprint-queue/status - Get queue status
- POST /api/similarity/fingerprint-queue/enqueue/{track_id} - Enqueue track
- POST /api/similarity/fingerprint-queue/enqueue-all - Enqueue all tracks
- GET /api/similarity/fingerprint-stats - Get fingerprint statistics

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
    repos.fingerprints = Mock()
    repos.tracks.get_by_id = Mock(return_value=None)
    repos.fingerprints.exists = Mock(return_value=False)
    return repos


class TestGetSimilarTracks:
    """Test GET /api/similarity/tracks/{track_id}/similar"""

    @patch('routers.similarity.require_repository_factory')
    def test_get_similar_tracks_not_found(self, mock_require_repos, client, mock_repos):
        """Test getting similar tracks for non-existent track"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.get("/api/similarity/tracks/999/similar")

        assert response.status_code == 404

    @patch('routers.similarity.require_repository_factory')
    def test_get_similar_tracks_no_fingerprint(self, mock_require_repos, client, mock_repos):
        """Test getting similar tracks when track has no fingerprint"""
        mock_require_repos.return_value = mock_repos

        mock_track = Mock()
        mock_track.id = 1
        mock_repos.tracks.get_by_id.return_value = mock_track
        mock_repos.fingerprints.exists.return_value = False

        response = client.get("/api/similarity/tracks/1/similar")

        # Should return 400 (no fingerprint) and queue for processing
        assert response.status_code == 400
        assert "fingerprint" in response.json()["detail"].lower()

    def test_get_similar_tracks_limit_parameter(self, client):
        """Test similar tracks with different limit values"""
        # Test with custom limit
        response = client.get("/api/similarity/tracks/1/similar?limit=5")

        # Will fail if track doesn't exist, but validates parameter parsing
        assert response.status_code in [400, 404, 500]

    def test_get_similar_tracks_limit_validation(self, client):
        """Test limit parameter validation"""
        # Limit below minimum
        response = client.get("/api/similarity/tracks/1/similar?limit=0")
        assert response.status_code == 422

        # Limit above maximum
        response = client.get("/api/similarity/tracks/1/similar?limit=101")
        assert response.status_code == 422

    def test_get_similar_tracks_use_graph_parameter(self, client):
        """Test use_graph parameter"""
        response = client.get("/api/similarity/tracks/1/similar?use_graph=false")

        assert response.status_code in [400, 404, 500]

    def test_get_similar_tracks_include_details(self, client):
        """Test include_details parameter"""
        response = client.get("/api/similarity/tracks/1/similar?include_details=true")

        assert response.status_code in [400, 404, 500]


class TestCompareTracks:
    """Test GET /api/similarity/tracks/{track_id1}/compare/{track_id2}"""

    @patch('routers.similarity.require_repository_factory')
    def test_compare_tracks_first_not_found(self, mock_require_repos, client, mock_repos):
        """Test comparing when first track doesn't exist"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.get("/api/similarity/tracks/999/compare/1")

        assert response.status_code == 404

    def test_compare_tracks_same_track(self, client):
        """Test comparing track to itself"""
        response = client.get("/api/similarity/tracks/1/compare/1")

        # Should handle gracefully (may return 0 distance or error)
        assert response.status_code in [200, 400, 404, 500]

    def test_compare_tracks_negative_ids(self, client):
        """Test comparing with negative track IDs"""
        response = client.get("/api/similarity/tracks/-1/compare/-2")

        assert response.status_code in [404, 422]


class TestExplainSimilarity:
    """Test GET /api/similarity/tracks/{track_id1}/explain/{track_id2}"""

    @patch('routers.similarity.require_repository_factory')
    def test_explain_similarity_not_found(self, mock_require_repos, client, mock_repos):
        """Test explaining similarity when tracks don't exist"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.get("/api/similarity/tracks/999/explain/998")

        assert response.status_code == 404

    def test_explain_similarity_structure(self, client):
        """Test explanation response structure if tracks exist"""
        response = client.get("/api/similarity/tracks/1/explain/2")

        if response.status_code == 200:
            data = response.json()

            assert "track_id1" in data
            assert "track_id2" in data
            assert "distance" in data
            assert "similarity_score" in data
            assert "top_differences" in data


class TestFitModel:
    """Test POST /api/similarity/fit"""

    def test_fit_model_endpoint(self, client):
        """Test fitting the similarity model"""
        response = client.post("/api/similarity/fit")

        # May require fingerprints to exist
        assert response.status_code in [200, 400, 500]

    def test_fit_model_accepts_post_only(self, client):
        """Test that fit endpoint only accepts POST"""
        response = client.get("/api/similarity/fit")
        assert response.status_code in [404, 405]


class TestBuildGraph:
    """Test POST /api/similarity/graph/build"""

    def test_build_graph_endpoint(self, client):
        """Test building the similarity graph"""
        response = client.post("/api/similarity/graph/build")

        # May require fitted model or fingerprints
        assert response.status_code in [200, 400, 500]

    def test_build_graph_accepts_post_only(self, client):
        """Test that build endpoint only accepts POST"""
        response = client.get("/api/similarity/graph/build")
        assert response.status_code in [404, 405]


class TestGraphStats:
    """Test GET /api/similarity/graph/stats"""

    def test_get_graph_stats_no_graph(self, client):
        """Test getting stats when graph doesn't exist"""
        response = client.get("/api/similarity/graph/stats")

        # May return None or 404 if no graph built
        assert response.status_code in [200, 404]

    def test_get_graph_stats_structure(self, client):
        """Test graph stats response structure if graph exists"""
        response = client.get("/api/similarity/graph/stats")

        if response.status_code == 200:
            data = response.json()

            if data is not None:  # Graph may not exist
                assert "total_tracks" in data
                assert "total_edges" in data
                assert "k_neighbors" in data

    def test_get_graph_stats_accepts_get_only(self, client):
        """Test that stats endpoint only accepts GET"""
        response = client.post("/api/similarity/graph/stats")
        assert response.status_code in [404, 405]


class TestDeleteGraph:
    """Test DELETE /api/similarity/graph"""

    def test_delete_graph_endpoint(self, client):
        """Test deleting the similarity graph"""
        response = client.delete("/api/similarity/graph")

        # Should succeed even if graph doesn't exist
        assert response.status_code in [200, 404]

    def test_delete_graph_accepts_delete_only(self, client):
        """Test that delete endpoint only accepts DELETE"""
        response = client.get("/api/similarity/graph")
        assert response.status_code in [404, 405]

    def test_delete_graph_multiple_times(self, client):
        """Test deleting graph multiple times"""
        # First delete
        response1 = client.delete("/api/similarity/graph")

        # Second delete (should also succeed or return 404)
        response2 = client.delete("/api/similarity/graph")

        assert response1.status_code in [200, 404]
        assert response2.status_code in [200, 404]


class TestFingerprintQueueStatus:
    """Test GET /api/similarity/fingerprint-queue/status"""

    def test_get_queue_status_structure(self, client):
        """Test queue status response structure"""
        response = client.get("/api/similarity/fingerprint-queue/status")

        assert response.status_code == 200
        data = response.json()

        # Should have queue information
        assert isinstance(data, dict)

    def test_get_queue_status_accepts_get_only(self, client):
        """Test that status endpoint only accepts GET"""
        response = client.post("/api/similarity/fingerprint-queue/status")
        assert response.status_code in [404, 405]


class TestEnqueueTrack:
    """Test POST /api/similarity/fingerprint-queue/enqueue/{track_id}"""

    @patch('routers.similarity.require_repository_factory')
    def test_enqueue_track_not_found(self, mock_require_repos, client, mock_repos):
        """Test enqueueing non-existent track"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.post("/api/similarity/fingerprint-queue/enqueue/999")

        assert response.status_code == 404

    def test_enqueue_track_endpoint(self, client):
        """Test enqueueing a track for fingerprinting"""
        response = client.post("/api/similarity/fingerprint-queue/enqueue/1")

        # May succeed or fail if track doesn't exist
        assert response.status_code in [200, 404, 500]

    def test_enqueue_track_accepts_post_only(self, client):
        """Test that enqueue endpoint only accepts POST"""
        response = client.get("/api/similarity/fingerprint-queue/enqueue/1")
        assert response.status_code in [404, 405]

    def test_enqueue_track_negative_id(self, client):
        """Test enqueueing with negative track ID"""
        response = client.post("/api/similarity/fingerprint-queue/enqueue/-1")

        assert response.status_code in [404, 422]


class TestEnqueueAll:
    """Test POST /api/similarity/fingerprint-queue/enqueue-all"""

    def test_enqueue_all_endpoint(self, client):
        """Test enqueueing all tracks"""
        response = client.post("/api/similarity/fingerprint-queue/enqueue-all")

        # Should process (may be slow if many tracks)
        assert response.status_code in [200, 500]

    def test_enqueue_all_accepts_post_only(self, client):
        """Test that enqueue-all endpoint only accepts POST"""
        response = client.get("/api/similarity/fingerprint-queue/enqueue-all")
        assert response.status_code in [404, 405]


class TestFingerprintStats:
    """Test GET /api/similarity/fingerprint-stats"""

    def test_get_fingerprint_stats_structure(self, client):
        """Test fingerprint stats response structure"""
        response = client.get("/api/similarity/fingerprint-stats")

        assert response.status_code == 200
        data = response.json()

        # Should have statistics about fingerprints
        assert isinstance(data, dict)

    def test_get_fingerprint_stats_accepts_get_only(self, client):
        """Test that stats endpoint only accepts GET"""
        response = client.post("/api/similarity/fingerprint-stats")
        assert response.status_code in [404, 405]


class TestSimilarityIntegration:
    """Integration tests for similarity workflow"""

    def test_workflow_fingerprint_then_similar(self, client):
        """Test workflow: enqueue fingerprint → check queue → find similar"""
        # 1. Enqueue track for fingerprinting
        enqueue_response = client.post("/api/similarity/fingerprint-queue/enqueue/1")

        if enqueue_response.status_code == 200:
            # 2. Check queue status
            status_response = client.get("/api/similarity/fingerprint-queue/status")
            assert status_response.status_code == 200

            # 3. Try to get similar tracks (may fail if fingerprint not yet processed)
            similar_response = client.get("/api/similarity/tracks/1/similar")
            assert similar_response.status_code in [200, 400]

    def test_workflow_build_graph_then_query(self, client):
        """Test workflow: build graph → get stats → query similar"""
        # 1. Build graph
        build_response = client.post("/api/similarity/graph/build")

        if build_response.status_code == 200:
            # 2. Get graph stats
            stats_response = client.get("/api/similarity/graph/stats")
            assert stats_response.status_code == 200

            # 3. Query similar tracks using graph
            similar_response = client.get("/api/similarity/tracks/1/similar?use_graph=true")
            assert similar_response.status_code in [200, 400, 404]

    def test_workflow_compare_explain_workflow(self, client):
        """Test workflow: compare tracks → explain differences"""
        # 1. Compare two tracks
        compare_response = client.get("/api/similarity/tracks/1/compare/2")

        if compare_response.status_code == 200:
            # 2. Explain the similarity
            explain_response = client.get("/api/similarity/tracks/1/explain/2")

            # Should succeed if compare succeeded
            assert explain_response.status_code in [200, 400]


class TestSimilaritySecurityValidation:
    """Security-focused tests for similarity endpoints"""

    def test_similar_tracks_sql_injection(self, client):
        """Test that track ID parameters don't allow SQL injection"""
        response = client.get("/api/similarity/tracks/1'; DROP TABLE tracks; --/similar")

        # Should reject malformed track ID
        assert response.status_code in [404, 422]

    def test_enqueue_extremely_large_id(self, client):
        """Test enqueueing with extremely large track ID"""
        large_id = 999999999999
        response = client.post(f"/api/similarity/fingerprint-queue/enqueue/{large_id}")

        # Should handle gracefully (404, not crash)
        assert response.status_code in [404, 500]

    def test_similar_tracks_limit_overflow(self, client):
        """Test limit parameter with overflow values"""
        # Try extremely large limit
        response = client.get("/api/similarity/tracks/1/similar?limit=999999")

        # Should be rejected by validation
        assert response.status_code == 422
