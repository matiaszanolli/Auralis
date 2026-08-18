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

#4716: this module absorbed the old, hard-skipped test_similarity_api.py
(written for the pre-#4270 single-router shape; skipped for requiring a
real app + a library pre-seeded with fingerprints, neither of which this
mocked-router style needs). Before deleting it:
  - Ported TestFingerprintRepositoryDualModeParametrized verbatim — despite
    living under the old file's module-level skip, it never touched the
    real app/DB (it exercises the already-mocked `mock_data_source`
    fixture), so it ran cleanly once moved here.
  - test_negative_limit / test_zero_k_neighbors / test_missing_track_comparison
    are already covered in spirit by this file's
    test_get_similar_tracks_limit_validation and
    test_compare_tracks_first_not_found (FastAPI Query validation / mocked
    not-found, respectively) — not re-ported as near-duplicates. A literal
    port of test_zero_k_neighbors (POST .../graph/build?k=0) was tried and
    dropped: it hits the same pre-existing Origin-check 403 from
    config/middleware.py that already accounts for most of this file's
    pytest-baseline.json entries for POST/DELETE routes under TestClient —
    unrelated to this consolidation, not fixed here.
  - test_find_similar_response_time / test_graph_query_faster_than_realtime
    (wall-clock timing assertions against a live DB) and
    test_fit_insufficient_fingerprints (asserts against real fingerprint
    counts) depend on the real-app/real-library style the old file used and
    don't translate to this mocked style — dropped rather than ported.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

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

        # 404, not 400: #4630 moved this precondition into
        # require_fingerprinted_tracks() (routers/similarity_common.py) so
        # /similar, /compare and /explain could not drift apart again, and it
        # signals a missing fingerprint with NotFoundError. The track is
        # enqueued on the way out, so the condition repairs itself.
        assert response.status_code == 404
        # Assert the fingerprint-specific detail, not just "fingerprint":
        # a nonexistent track is also a 404 ("Track 1 not found"), and these
        # two causes are deliberately distinguished by the same helper.
        assert "does not have a fingerprint" in response.json()["detail"]

    def test_get_similar_tracks_limit_parameter(self, client):
        """Test similar tracks with different limit values"""
        # Test with custom limit
        response = client.get("/api/similarity/tracks/1/similar?limit=5")

        # Track 1 doesn't exist in the test library, but validates parameter parsing
        assert response.status_code == 404

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

        assert response.status_code == 404

    def test_get_similar_tracks_include_details(self, client):
        """Test include_details parameter"""
        response = client.get("/api/similarity/tracks/1/similar?include_details=true")

        assert response.status_code == 404


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

        # Track 1 doesn't exist in the test library
        assert response.status_code == 404

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

        # Test library has fewer than min_samples fingerprints
        assert response.status_code == 400

    def test_fit_model_accepts_post_only(self, client):
        """Test that fit endpoint only accepts POST"""
        response = client.get("/api/similarity/fit")
        assert response.status_code in [404, 405]


class TestBuildGraph:
    """Test POST /api/similarity/graph/build"""

    def test_build_graph_endpoint(self, client):
        """Test building the similarity graph"""
        response = client.post("/api/similarity/graph/build")

        # No fitted similarity system in the test library
        assert response.status_code == 503

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

    @patch('routers.fingerprint_queue.require_repository_factory')
    def test_enqueue_track_not_found(self, mock_require_repos, client, mock_repos):
        """Test enqueueing non-existent track"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.post("/api/similarity/fingerprint-queue/enqueue/999")

        assert response.status_code == 404

    @patch('routers.fingerprint_queue.require_repository_factory')
    def test_enqueue_track_endpoint(self, mock_require_repos, client, mock_repos):
        """Test enqueueing a track for fingerprinting"""
        # This asserted 404 on the premise that "track 1 doesn't exist in the
        # test library". The `client` fixture runs the real lifespan against
        # the developer's real ~/.auralis/library.db, where track 1 generally
        # does exist, so that premise was environment-dependent -- it went
        # unnoticed only because the POST was rejected by the Origin-check
        # middleware before it ever reached the route (#5089).
        #
        # Mock the repositories like the sibling test_enqueue_track_not_found
        # above so the happy path is exercised deterministically, and mock the
        # queue too: whether track 1 is *already* queued depends on what ran
        # earlier in the session (a missing-fingerprint 404 from /similar
        # enqueues it as a side effect), which would otherwise flip `reason`
        # between "Added to queue" and "Already queued or processing". It also
        # stops this test feeding the real background fingerprint worker.
        mock_require_repos.return_value = mock_repos

        mock_track = Mock()
        mock_track.id = 1
        mock_repos.tracks.get_by_id.return_value = mock_track
        mock_repos.fingerprints.exists.return_value = False

        mock_queue = Mock()
        mock_queue.enqueue.return_value = True

        with patch('analysis.fingerprint_queue.get_fingerprint_queue', return_value=mock_queue):
            response = client.post("/api/similarity/fingerprint-queue/enqueue/1")

        assert response.status_code == 200
        # Exactly the EnqueueFingerprintResponse shape the frontend consumes
        # (routers/fingerprint_queue.py) -- track_id is populated on this
        # branch and omitted only on the already-fingerprinted early return.
        assert response.json() == {
            "enqueued": True,
            "track_id": 1,
            "reason": "Added to queue",
        }
        mock_queue.enqueue.assert_called_once_with(1)

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
        # Real side effect (#5089): the `client` fixture runs the full lifespan
        # against the developer's real ~/.auralis/library.db, so this genuinely
        # feeds the background fingerprint worker -- it was inert only while
        # the POST was Origin-rejected. Tracks whose audio cannot be
        # fingerprinted leave an in-progress claim placeholder row behind
        # (lufs == PLACEHOLDER_LUFS_SENTINEL); FingerprintRepository.exists()
        # filters those out (#4822), so /similar keeps correctly reporting
        # "no fingerprint" for them rather than treating a claim as complete.
        response = client.post("/api/similarity/fingerprint-queue/enqueue-all")

        # Should process (may be slow if many tracks)
        assert response.status_code == 200

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

            # 3. Try to get similar tracks. Fingerprint generation is
            #    asynchronous, so it is normally not ready by the time this
            #    runs: /similar reports that as a 404 naming the missing
            #    fingerprint (#4630 -- require_fingerprinted_tracks() raises
            #    NotFoundError; it was never a 400) and re-enqueues the track.
            #    Assert that specific detail instead of widening the status
            #    allow-list, because "Track 1 not found" is a 404 too -- and a
            #    just-enqueued track coming back as nonexistent would mean the
            #    two routes disagree about the library, which must still fail.
            #    This branch only became reachable once the enqueue above
            #    stopped being rejected by the Origin check (#5089).
            similar_response = client.get("/api/similarity/tracks/1/similar")

            if similar_response.status_code == 404:
                assert "does not have a fingerprint" in similar_response.json()["detail"]
            else:
                # Fingerprint already complete: either similarity results, or
                # 503 if the similarity system was never fitted for this library.
                assert similar_response.status_code in (200, 503)

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
        assert response.status_code == 404

    def test_similar_tracks_limit_overflow(self, client):
        """Test limit parameter with overflow values"""
        # Try extremely large limit
        response = client.get("/api/similarity/tracks/1/similar?limit=999999")

        # Should be rejected by validation
        assert response.status_code == 422


class TestBlockingCallsOffloaded:
    """Verify CPU-bound calls run in a thread, not on the event loop (fixes #2738)"""

    @pytest.mark.asyncio
    async def test_build_graph_uses_to_thread(self):
        """build_similarity_graph calls graph_builder.build_graph via asyncio.to_thread"""
        from routers.similarity_graph import create_similarity_graph_router

        mock_graph_builder = Mock()
        mock_stats = Mock()
        mock_stats.to_dict.return_value = {
            "total_tracks": 10,
            "total_edges": 30,
            "k_neighbors": 3,
            "avg_distance": 0.5,
            "min_distance": 0.1,
            "max_distance": 0.9,
            "build_time_seconds": 1.0,
        }
        mock_graph_builder.build_graph.return_value = mock_stats

        router = create_similarity_graph_router(
            get_graph_builder=lambda: mock_graph_builder,
        )

        # Find the build endpoint handler
        handler = None
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/api/similarity/graph/build":
                handler = route.endpoint
                break

        assert handler is not None, "Could not find /graph/build endpoint"

        with patch("routers.similarity_graph.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = mock_stats

            await handler(k=5, clear_existing=True)

            mock_to_thread.assert_called_once_with(
                mock_graph_builder.build_graph, k=5, clear_existing=True
            )

    @pytest.mark.asyncio
    async def test_fit_uses_to_thread(self):
        """fit_similarity_system calls similarity.fit via asyncio.to_thread"""
        from routers.similarity import create_similarity_router

        mock_similarity = Mock()
        mock_similarity.is_fitted.return_value = False

        mock_repos = Mock()
        mock_repos.fingerprints.get_count.return_value = 100

        router = create_similarity_router(
            get_similarity_system=lambda: mock_similarity,
            get_graph_builder=Mock(),
            get_repository_factory=lambda: mock_repos,
        )

        # Find the fit endpoint handler
        handler = None
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/api/similarity/fit":
                handler = route.endpoint
                break

        assert handler is not None, "Could not find /fit endpoint"

        # Make to_thread transparent so the endpoint's real control flow runs:
        # is_fitted() -> False, then get_count() -> 100 (>= min_samples), then fit().
        # The endpoint legitimately offloads is_fitted/get_count/fit, so assert that
        # fit was *among* the to_thread calls rather than the only one.
        async def fake_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        with patch("routers.similarity.asyncio.to_thread", side_effect=fake_to_thread) as mock_to_thread, \
             patch("routers.similarity.require_repository_factory", return_value=mock_repos):

            await handler(min_samples=10)

            mock_to_thread.assert_any_call(mock_similarity.fit)


@pytest.mark.phase5c
class TestFingerprintRepositoryDualModeParametrized:
    """Parametrized dual-mode tests for the fingerprints repository interface,
    ported from the retired test_similarity_api.py (#4716).

    Unlike the rest of that file, these never needed a real app/DB — they
    exercise `mock_data_source` (already mocked for both LibraryManager and
    RepositoryFactory) and were caught by the file's blanket module-level
    skip only because they lived alongside the genuinely DB-dependent
    integration tests, not because they needed one themselves.
    """

    def test_fingerprint_repository_interface(self, mock_data_source):
        """Both LibraryManager and RepositoryFactory expose a fingerprints
        repository with get_all/get_by_id."""
        mode, source = mock_data_source

        assert hasattr(source, 'fingerprints'), f"{mode} missing fingerprints repository"
        assert hasattr(source.fingerprints, 'get_all'), f"{mode}.fingerprints missing get_all"
        assert hasattr(source.fingerprints, 'get_by_id'), f"{mode}.fingerprints missing get_by_id"

    def test_fingerprint_stats_operation(self, mock_data_source):
        """Both modes support fingerprint stats retrieval with the same shape."""
        mode, source = mock_data_source

        stats = {
            'total': 100,
            'fingerprinted': 75,
            'pending': 25,
            'progress_percent': 75
        }
        source.fingerprints.get_fingerprint_stats = Mock(return_value=stats)

        result = source.fingerprints.get_fingerprint_stats()

        assert result['total'] == 100, f"{mode}: Total count mismatch"
        assert result['fingerprinted'] == 75, f"{mode}: Fingerprinted count mismatch"
        assert result['pending'] == 25, f"{mode}: Pending count mismatch"
        assert result['progress_percent'] == 75, f"{mode}: Progress percent mismatch"
        source.fingerprints.get_fingerprint_stats.assert_called_once()

    def test_fingerprint_get_by_id_interface(self, mock_data_source):
        """Both modes return fingerprint data consistently from get_by_id."""
        mode, source = mock_data_source

        fingerprint = Mock()
        fingerprint.id = 1
        fingerprint.track_id = 100
        fingerprint.fingerprint_data = b"test_fingerprint"

        source.fingerprints.get_by_id = Mock(return_value=fingerprint)

        result = source.fingerprints.get_by_id(1)

        assert result.id == 1, f"{mode}: Fingerprint ID mismatch"
        assert result.track_id == 100, f"{mode}: Track ID mismatch"
        assert result.fingerprint_data == b"test_fingerprint", f"{mode}: Fingerprint data mismatch"
