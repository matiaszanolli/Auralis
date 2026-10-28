"""
Tests for Albums REST API
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the albums browsing and management endpoints.

Phase 6B: Migrated to RepositoryFactory Pattern
This file uses the Phase 6B RepositoryFactory pattern:
1. Tests mock require_repository_factory to inject mock repos
2. The mock_repos fixture provides a mock RepositoryFactory
3. Tests validate the albums API with the new dependency injection pattern
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from auralis.analysis.fingerprint.schema import CENTROID_NORMALIZATION_HZ, ROLLOFF_NORMALIZATION_HZ
from auralis.library.models import Album, Artist, Track

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

# Phase 5B.1: Migration to conftest.py fixtures
# Removed local client() fixture - now using conftest.py fixture
# All tests automatically use the fixture from parent conftest.py


@pytest.fixture
def album_row():
    """A real (transient) Album: serialize_object() calls its own to_dict()."""
    return Album(
        id=1,
        title="Test Album",
        artist=Artist(name="Test Artist"),
        artist_id=1,
        year=2024,
        total_tracks=2,
        total_discs=1,
        artwork_path=None,
        avg_dr_rating=12.0,
        avg_lufs=-14.0,
        mastering_consistency=0.85,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        # Album.to_dict() derives track_count/total_duration from `tracks` when
        # the query supplied no SQL aggregates (#4777).
        tracks=[Track(duration=180), Track(duration=200)],
    )


@pytest.fixture
def track_row():
    """A real (transient) Track belonging to its own album."""
    return Track(
        id=1,
        title="Test Track",
        album=Album(id=1, title="Test Album"),
        duration=180,
        track_number=1,
        disc_number=1,
        favorite=False,  # column default applies only at flush
    )


@pytest.fixture
def mock_repos():
    """Create a mock RepositoryFactory for patching require_repository_factory.

    Phase 6B: The albums router uses RepositoryFactory instead of LibraryManager.
    This fixture provides the mock object that require_repository_factory returns.
    """
    repos = Mock()
    repos.albums = Mock()
    repos.albums.get_all = Mock(return_value=([], 0))
    repos.albums.get_by_id = Mock(return_value=None)
    repos.albums.search = Mock(return_value=[])
    return repos


class TestGetAlbums:
    """Test GET /api/albums endpoint"""

    def test_get_albums_default_pagination(self, client):
        """Test getting albums with default pagination"""
        response = client.get("/api/albums")

        assert response.status_code == 200

        if response.status_code == 200:
            data = response.json()
            assert "albums" in data
            assert "total" in data
            assert "offset" in data
            assert "limit" in data
            assert "has_more" in data
            assert isinstance(data["albums"], list)

    def test_get_albums_with_limit(self, client):
        """Test getting albums with custom limit"""
        response = client.get("/api/albums?limit=5")

        assert response.status_code == 200

        if response.status_code == 200:
            data = response.json()
            assert data["limit"] == 5
            assert len(data["albums"]) <= 5

    def test_get_albums_with_offset(self, client):
        """Test getting albums with offset"""
        response = client.get("/api/albums?limit=10&offset=5")

        assert response.status_code == 200

        if response.status_code == 200:
            data = response.json()
            assert data["offset"] == 5
            assert data["limit"] == 10

    def test_get_albums_with_search(self, client):
        """Test searching albums by name"""
        response = client.get("/api/albums?search=test")

        assert response.status_code == 200

        if response.status_code == 200:
            data = response.json()
            assert "albums" in data

    def test_get_albums_order_by_title(self, client):
        """Test ordering albums by title"""
        response = client.get("/api/albums?order_by=title")

        assert response.status_code == 200

        if response.status_code == 200:
            data = response.json()
            assert "albums" in data

    def test_get_albums_order_by_year(self, client):
        """Test ordering albums by year"""
        response = client.get("/api/albums?order_by=year")

        assert response.status_code == 200

    def test_get_albums_invalid_limit(self, client):
        """Test getting albums with invalid limit (too high)"""
        response = client.get("/api/albums?limit=500")

        # limit is a Query(..., le=200) — FastAPI/Pydantic rejects this at
        # the framework level before the handler ever runs.
        assert response.status_code == 422

    def test_get_albums_negative_offset(self, client):
        """Test getting albums with negative offset"""
        response = client.get("/api/albums?offset=-1")

        # offset is a Query(..., ge=0) — FastAPI/Pydantic rejects this at
        # the framework level before the handler ever runs.
        assert response.status_code == 422

    def test_get_albums_with_mocked_data(self, client, album_row, mock_repos):
        """Test albums endpoint with mocked repository factory"""
        mock_repos.albums.get_all.return_value = ([album_row], 1)

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums?limit=50&offset=0")

            assert response.status_code == 200
            data = response.json()

            assert len(data["albums"]) == 1
            assert data["total"] == 1
            assert data["albums"][0]["id"] == 1
            assert data["albums"][0]["title"] == "Test Album"
            assert data["albums"][0]["track_count"] == 2
            assert data["has_more"] == False

    def test_get_albums_pagination_has_more(self, client, album_row, mock_repos):
        """Test has_more flag in pagination"""
        # Return 50 albums, total 100
        mock_albums = [album_row] * 50
        mock_repos.albums.get_all.return_value = (mock_albums, 100)

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums?limit=50&offset=0")

            assert response.status_code == 200
            data = response.json()

            assert data["has_more"] == True
            assert data["total"] == 100


class TestGetAlbumById:
    """Test GET /api/albums/{album_id} endpoint"""

    def test_get_album_by_id_success(self, client, album_row, mock_repos):
        """Test getting a specific album by ID"""
        mock_repos.albums.get_by_id.return_value = album_row

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums/1")

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == 1
            assert data["title"] == "Test Album"
            assert data["artist"] == "Test Artist"

            # Same snake_case shape as the GET /api/albums listing (#4679).
            # #4423 gave this endpoint a camelCase shape of its own for a
            # frontend consumer that never materialised, leaving one entity on
            # the wire in two incompatible casings against a single declared TS
            # contract. The camelCase serializer and response model are gone.
            assert "track_count" in data
            assert "trackCount" not in data
            assert "artworkUrl" not in data
            assert "totalDuration" not in data
            assert "artistId" not in data
            # The deleted AlbumDetailResponse declared `genre` long after the
            # serializer stopped emitting it (#4709), so the endpoint shipped a
            # permanent null. Album has no genre column.
            assert "genre" not in data

    def test_get_album_by_id_not_found(self, client, mock_repos):
        """Test getting non-existent album"""
        mock_repos.albums.get_by_id.return_value = None

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums/9999")

            assert response.status_code == 404

    def test_get_album_by_id_invalid_id(self, client):
        """Test getting album with invalid ID"""
        response = client.get("/api/albums/invalid")

        # Should return 422 for validation error
        assert response.status_code == 422


class TestGetAlbumTracks:
    """Test GET /api/albums/{album_id}/tracks endpoint"""

    def test_get_album_tracks_success(self, client, album_row, track_row, mock_repos):
        """Test getting tracks for an album"""
        album_row.tracks = [track_row, track_row]
        mock_repos.albums.get_by_id.return_value = album_row

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums/1/tracks")

            assert response.status_code == 200
            data = response.json()

            assert data["album_id"] == 1
            assert data["album_title"] == "Test Album"
            assert data["artist"] == "Test Artist"
            assert data["total_tracks"] == 2
            assert len(data["tracks"]) == 2
            assert "year" in data

    def test_get_album_tracks_empty(self, client, album_row, mock_repos):
        """Test getting tracks for album with no tracks"""
        album_row.tracks = []
        mock_repos.albums.get_by_id.return_value = album_row

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums/1/tracks")

            assert response.status_code == 200
            data = response.json()

            assert data["total_tracks"] == 0
            assert len(data["tracks"]) == 0

    def test_get_album_tracks_not_found(self, client, mock_repos):
        """Test getting tracks for non-existent album"""
        mock_repos.albums.get_by_id.return_value = None

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums/9999/tracks")

            assert response.status_code == 404

    def test_get_album_tracks_sorted(self, client, album_row, mock_repos):
        """Test that tracks are sorted by disc and track number"""
        track1 = Track(id=1, title="Track 1", album=album_row, duration=180,
                       track_number=2, disc_number=1, favorite=False)
        track2 = Track(id=2, title="Track 2", album=album_row, duration=200,
                       track_number=1, disc_number=1, favorite=False)

        album_row.tracks = [track1, track2]
        mock_repos.albums.get_by_id.return_value = album_row

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums/1/tracks")

            assert response.status_code == 200
            data = response.json()

            # Should be sorted by track number
            assert len(data["tracks"]) == 2


class TestAlbumsAPIIntegration:
    """Integration tests for albums API"""

    def test_albums_workflow(self, client, album_row, track_row, mock_repos):
        """Test complete workflow: list albums -> get album -> get tracks"""
        album_row.tracks = [track_row]

        # Configure mock for all steps
        mock_repos.albums.get_all.return_value = ([album_row], 1)
        mock_repos.albums.get_by_id.return_value = album_row

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            # Step 1: List albums
            response = client.get("/api/albums")
            assert response.status_code == 200
            albums = response.json()["albums"]

            if albums:
                album_id = albums[0]["id"]

                # Step 2: Get album details
                response = client.get(f"/api/albums/{album_id}")
                assert response.status_code == 200

                # Step 3: Get album tracks
                response = client.get(f"/api/albums/{album_id}/tracks")
                assert response.status_code == 200
                tracks_data = response.json()
                assert "tracks" in tracks_data

    def test_albums_search_and_retrieve(self, client, album_row, mock_repos):
        """Test searching for album and retrieving it"""
        mock_repos.albums.search.return_value = ([album_row], 1)

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            # Search for album
            response = client.get("/api/albums?search=Test")
            assert response.status_code == 200

            if response.status_code == 200:
                data = response.json()
                assert "albums" in data


class TestAlbumsErrorHandling:
    """Test error handling in albums API"""

    def test_albums_database_error(self, client, mock_repos):
        """Test handling of database errors"""
        mock_repos.albums.get_all.side_effect = Exception("Database connection error")

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums")

            assert response.status_code == 500

    def test_album_by_id_database_error(self, client, mock_repos):
        """Test handling of database errors when getting album by ID"""
        mock_repos.albums.get_by_id.side_effect = Exception("Database error")

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums/1")

            assert response.status_code == 500


# ============================================================
# Phase 5C: Dual-Mode Backend Testing Patterns
# ============================================================
class TestGetAlbumFingerprint:
    """Test GET /api/albums/{id}/fingerprint endpoint"""

    def test_fingerprint_success(self, client, album_row, mock_repos):
        """Known album with fingerprinted tracks returns 200 with fingerprint"""
        # get_summary() supplies the SQL track count, never Album.tracks (#5873)
        album_row.track_count_expr = 1
        mock_repos.albums.get_summary.return_value = album_row

        fp = Mock()
        # Set all 25 DB columns to known values
        for col in ['sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
                     'upper_mid_pct', 'presence_pct', 'air_pct', 'lufs',
                     'crest_db', 'bass_mid_ratio', 'tempo_bpm',
                     'rhythm_stability', 'transient_density', 'silence_ratio',
                     'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
                     'harmonic_ratio', 'pitch_stability', 'chroma_energy',
                     'dynamic_range_variation', 'loudness_variation_std',
                     'peak_consistency', 'stereo_width', 'phase_correlation']:
            setattr(fp, col, 0.5)

        mock_repos.fingerprints = Mock()
        # One join by album id (#5873) instead of a track-id list built from
        # the hydrated album.
        mock_repos.fingerprints.get_by_album_ids.return_value = {1: [fp]}

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums/1/fingerprint")

        assert response.status_code == 200
        data = response.json()
        assert data["album_id"] == 1
        assert data["fingerprinted_track_count"] == 1
        assert "fingerprint" in data
        assert data["fingerprint"]["lufs"] == 0.5
        # spectral_centroid/spectral_rolloff are stored normalized [0, 1] but
        # served in Hz per FingerprintVectorResponse's documented contract
        # (#5470) -- a raw 0.5 must not leak through unconverted.
        assert data["fingerprint"]["spectral_centroid"] == pytest.approx(0.5 * CENTROID_NORMALIZATION_HZ)
        assert data["fingerprint"]["spectral_rolloff"] == pytest.approx(0.5 * ROLLOFF_NORMALIZATION_HZ)

    def test_fingerprint_album_not_found(self, client, mock_repos):
        """Unknown album ID returns 404"""
        mock_repos.albums.get_summary.return_value = None

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums/999/fingerprint")

        assert response.status_code == 404

    def test_fingerprint_no_fingerprints(self, client, album_row, mock_repos):
        """Album with tracks but no fingerprints returns 404"""
        album_row.track_count_expr = 1
        mock_repos.albums.get_summary.return_value = album_row

        mock_repos.fingerprints = Mock()
        mock_repos.fingerprints.get_by_album_ids.return_value = {}

        with patch('routers.repo_deps.require_repository_factory', return_value=mock_repos):
            response = client.get("/api/albums/1/fingerprint")

        assert response.status_code == 404
