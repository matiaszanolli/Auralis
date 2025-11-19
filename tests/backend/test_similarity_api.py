# -*- coding: utf-8 -*-

"""
Tests for Similarity API Endpoints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the REST API endpoints for the similarity system

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

NOTE: Integration tests for similarity API that require:
1. Full FastAPI application startup (library_manager initialization)
2. Fingerprints to exist in the library database
3. Similarity system to be fitted

Status: SKIPPED
- Tests are integration tests with external dependencies
- Require full application startup in test context
- Need pre-existing fingerprints in library
- Need fitted similarity system

To enable these tests in future:
1. Mock the library_manager and fingerprint system
2. Or run against live instance with populated library
3. Ensure similarity router is properly initialized during testing
"""

import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from auralis.library import LibraryManager

# Skip all tests in this file - integration tests with external dependencies
pytestmark = pytest.mark.skip(
    reason="Integration tests for similarity API. Requires full application startup "
           "and library with fingerprints. Tests skipped to keep CI fast; run manually with populated library."
)

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture(scope="module")
def client():
    """Create test client for FastAPI app"""
    from main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def library():
    """Create library manager instance"""
    return LibraryManager()


@pytest.fixture(scope="module")
def fingerprint_count(library):
    """Get count of available fingerprints"""
    return library.fingerprints.get_count()


@pytest.fixture(scope="module")
def sample_track_ids(library, fingerprint_count):
    """Get sample track IDs that have fingerprints"""
    if fingerprint_count < 2:
        pytest.skip("Need at least 2 fingerprints for API tests")

    fingerprints = library.fingerprints.get_all(limit=5)
    return [fp.track_id for fp in fingerprints]


class TestSimilarityAPI:
    """Test suite for similarity API endpoints"""

    def test_find_similar_tracks_endpoint(self, client, sample_track_ids):
        """Test GET /api/similarity/tracks/{id}/similar"""
        track_id = sample_track_ids[0]

        response = client.get(f"/api/similarity/tracks/{track_id}/similar?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 3

        # Check structure of each result
        for track in data:
            assert "track_id" in track
            assert "distance" in track
            assert "similarity_score" in track
            assert "title" in track
            assert "artist" in track

            # Validate ranges
            assert track["distance"] >= 0.0
            assert 0.0 <= track["similarity_score"] <= 1.0

    def test_find_similar_tracks_with_graph(self, client, sample_track_ids):
        """Test finding similar tracks using K-NN graph"""
        track_id = sample_track_ids[0]

        response = client.get(
            f"/api/similarity/tracks/{track_id}/similar?limit=3&use_graph=true"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_find_similar_tracks_invalid_id(self, client):
        """Test with invalid track ID"""
        response = client.get("/api/similarity/tracks/999999/similar")

        # Should return error or empty list
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert response.json() == []

    def test_compare_tracks_endpoint(self, client, sample_track_ids):
        """Test GET /api/similarity/tracks/{id1}/compare/{id2}"""
        if len(sample_track_ids) < 2:
            pytest.skip("Need at least 2 tracks")

        track_id1 = sample_track_ids[0]
        track_id2 = sample_track_ids[1]

        response = client.get(
            f"/api/similarity/tracks/{track_id1}/compare/{track_id2}"
        )

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "track_id1" in data
        assert "track_id2" in data
        assert "distance" in data
        assert "similarity_score" in data

        # Validate values
        assert data["track_id1"] == track_id1
        assert data["track_id2"] == track_id2
        assert data["distance"] >= 0.0
        assert 0.0 <= data["similarity_score"] <= 1.0

    def test_compare_same_track(self, client, sample_track_ids):
        """Test comparing a track with itself"""
        track_id = sample_track_ids[0]

        response = client.get(
            f"/api/similarity/tracks/{track_id}/compare/{track_id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Same track should have distance ~0 and similarity ~1
        assert data["distance"] < 0.01
        assert data["similarity_score"] > 0.99

    def test_explain_similarity_endpoint(self, client, sample_track_ids):
        """Test GET /api/similarity/tracks/{id1}/explain/{id2}"""
        if len(sample_track_ids) < 2:
            pytest.skip("Need at least 2 tracks")

        track_id1 = sample_track_ids[0]
        track_id2 = sample_track_ids[1]

        response = client.get(
            f"/api/similarity/tracks/{track_id1}/explain/{track_id2}?top_n=3"
        )

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "track_id1" in data
        assert "track_id2" in data
        assert "distance" in data
        assert "similarity_score" in data
        assert "top_differences" in data
        assert "all_contributions" in data

        # Top differences should be limited to 3
        assert len(data["top_differences"]) <= 3

        # Check top differences structure
        for diff in data["top_differences"]:
            assert "dimension" in diff
            assert "contribution" in diff
            assert "value1" in diff
            assert "value2" in diff
            assert "difference" in diff

        # Top differences should be sorted by contribution (descending)
        contributions = [d["contribution"] for d in data["top_differences"]]
        assert contributions == sorted(contributions, reverse=True)

    def test_build_graph_endpoint(self, client, fingerprint_count):
        """Test POST /api/similarity/graph/build"""
        if fingerprint_count < 5:
            pytest.skip("Need at least 5 fingerprints to build graph")

        response = client.post("/api/similarity/graph/build?k=3")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "total_tracks" in data
        assert "total_edges" in data
        assert "k_neighbors" in data
        assert "avg_distance" in data
        assert "build_time_seconds" in data

        # Validate values
        assert data["total_tracks"] > 0
        assert data["total_edges"] > 0
        assert data["k_neighbors"] == 3
        assert data["avg_distance"] >= 0.0
        assert data["build_time_seconds"] >= 0.0

    def test_get_graph_stats_endpoint(self, client):
        """Test GET /api/similarity/graph/stats"""
        response = client.get("/api/similarity/graph/stats")

        # Should return stats or 404 if no graph exists
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "total_tracks" in data
            assert "total_edges" in data
            assert "k_neighbors" in data

    def test_fit_similarity_system_endpoint(self, client, fingerprint_count):
        """Test POST /api/similarity/fit"""
        if fingerprint_count < 5:
            pytest.skip("Need at least 5 fingerprints to fit")

        response = client.post("/api/similarity/fit?min_samples=5")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "fitted" in data
        assert "total_fingerprints" in data

        # Validate values
        assert data["fitted"] is True
        assert data["total_fingerprints"] >= 5

    def test_fit_insufficient_fingerprints(self, client):
        """Test fitting with insufficient fingerprints"""
        # Request fit with impossibly high min_samples
        response = client.post("/api/similarity/fit?min_samples=100000")

        assert response.status_code in [200, 400]

        if response.status_code == 200:
            data = response.json()
            assert data["fitted"] is False


class TestSimilarityAPIErrorHandling:
    """Test error handling in similarity API"""

    def test_negative_limit(self, client, sample_track_ids):
        """Test with negative limit parameter"""
        track_id = sample_track_ids[0]

        response = client.get(f"/api/similarity/tracks/{track_id}/similar?limit=-1")

        # Should handle gracefully (return error or use default)
        assert response.status_code in [200, 400, 422]

    def test_zero_k_neighbors(self, client):
        """Test building graph with k=0"""
        response = client.post("/api/similarity/graph/build?k=0")

        # Should return error
        assert response.status_code in [400, 422]

    def test_missing_track_comparison(self, client):
        """Test comparing non-existent tracks"""
        response = client.get("/api/similarity/tracks/999999/compare/999998")

        # Should return error
        assert response.status_code in [404, 400]


class TestSimilarityAPIPerformance:
    """Test performance characteristics of similarity API"""

    def test_find_similar_response_time(self, client, sample_track_ids):
        """Test that similarity search completes in reasonable time"""
        import time

        track_id = sample_track_ids[0]

        start_time = time.time()
        response = client.get(f"/api/similarity/tracks/{track_id}/similar?limit=5")
        end_time = time.time()

        assert response.status_code == 200

        # Should complete in under 5 seconds (generous limit)
        # With K-NN graph: <100ms
        # Without: <5s
        response_time = end_time - start_time
        assert response_time < 5.0

    def test_graph_query_faster_than_realtime(self, client, sample_track_ids, fingerprint_count):
        """Test that graph queries are faster than real-time search"""
        import time

        if fingerprint_count < 5:
            pytest.skip("Need at least 5 fingerprints")

        track_id = sample_track_ids[0]

        # Build graph first
        client.post("/api/similarity/graph/build?k=5")

        # Time with graph
        start_time = time.time()
        response_graph = client.get(
            f"/api/similarity/tracks/{track_id}/similar?limit=5&use_graph=true"
        )
        graph_time = time.time() - start_time

        # Time without graph
        start_time = time.time()
        response_realtime = client.get(
            f"/api/similarity/tracks/{track_id}/similar?limit=5&use_graph=false"
        )
        realtime_time = time.time() - start_time

        assert response_graph.status_code == 200
        assert response_realtime.status_code == 200

        # Graph should be faster (or at least not slower)
        # Note: This might fail with very small datasets
        assert graph_time <= realtime_time * 2  # Allow 2x margin


@pytest.mark.integration
class TestSimilarityAPIIntegration:
    """Integration tests for complete similarity workflows"""

    def test_complete_similarity_workflow(self, client, fingerprint_count):
        """Test complete workflow: fit → build graph → query"""
        if fingerprint_count < 5:
            pytest.skip("Need at least 5 fingerprints")

        # Step 1: Fit similarity system
        response = client.post("/api/similarity/fit?min_samples=5")
        assert response.status_code == 200
        assert response.json()["fitted"] is True

        # Step 2: Build K-NN graph
        response = client.post("/api/similarity/graph/build?k=3")
        assert response.status_code == 200
        graph_stats = response.json()
        assert graph_stats["total_edges"] > 0

        # Step 3: Get graph stats
        response = client.get("/api/similarity/graph/stats")
        assert response.status_code == 200
        stats = response.json()
        assert stats["total_edges"] == graph_stats["total_edges"]

        # Step 4: Query similar tracks
        fingerprints = LibraryManager().fingerprints.get_all(limit=1)
        track_id = fingerprints[0].track_id

        response = client.get(
            f"/api/similarity/tracks/{track_id}/similar?limit=3&use_graph=true"
        )
        assert response.status_code == 200
        similar_tracks = response.json()
        assert len(similar_tracks) > 0

    def test_similarity_consistency(self, client, sample_track_ids):
        """Test that similarity calculations are consistent"""
        if len(sample_track_ids) < 2:
            pytest.skip("Need at least 2 tracks")

        track_id1 = sample_track_ids[0]
        track_id2 = sample_track_ids[1]

        # Compare A to B
        response1 = client.get(f"/api/similarity/tracks/{track_id1}/compare/{track_id2}")
        comparison1 = response1.json()

        # Compare B to A (should be same result)
        response2 = client.get(f"/api/similarity/tracks/{track_id2}/compare/{track_id1}")
        comparison2 = response2.json()

        # Distance should be symmetric
        assert abs(comparison1["distance"] - comparison2["distance"]) < 0.0001
        assert abs(comparison1["similarity_score"] - comparison2["similarity_score"]) < 0.0001
