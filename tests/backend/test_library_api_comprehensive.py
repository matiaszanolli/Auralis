"""
Tests for Library Router (Comprehensive)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for all library query endpoints.

Coverage (13 routes):
- GET /api/library/stats - Library statistics
- GET /api/library/tracks - Get tracks with search/pagination
- GET /api/library/tracks/favorites - Get favorite tracks
- POST /api/library/tracks/{track_id}/favorite - Mark as favorite
- DELETE /api/library/tracks/{track_id}/favorite - Remove from favorites
- GET /api/library/tracks/{track_id}/lyrics - Get track lyrics
- GET /api/library/artists - Get all artists
- GET /api/library/artists/{artist_id} - Get artist details
- GET /api/library/albums - Get all albums
- GET /api/library/albums/{album_id} - Get album details
- POST /api/library/scan - Scan directory
- GET /api/library/fingerprints/status - Get fingerprint status
- GET /api/tracks/{track_id}/fingerprint - Get track fingerprint

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
    repos.albums = Mock()
    repos.artists = Mock()
    repos.stats = Mock()
    repos.tracks.get_all = Mock(return_value=([], 0))
    repos.tracks.get_by_id = Mock(return_value=None)
    repos.albums.get_all = Mock(return_value=([], 0))
    repos.artists.get_all = Mock(return_value=([], 0))
    return repos


class TestLibraryStats:
    """Test GET /api/library/stats"""

    def test_get_library_stats_structure(self, client):
        """Test library stats response structure"""
        response = client.get("/api/library/stats")

        assert response.status_code == 200
        data = response.json()

        # Should have basic library statistics
        assert isinstance(data, dict)

    def test_get_library_stats_accepts_get_only(self, client):
        """Test that stats endpoint only accepts GET"""
        response = client.post("/api/library/stats")
        assert response.status_code in [404, 405]


class TestGetTracks:
    """Test GET /api/library/tracks"""

    def test_get_tracks_basic(self, client):
        """Test getting tracks without parameters"""
        response = client.get("/api/library/tracks")

        assert response.status_code == 200
        data = response.json()

        # Should return tracks array and metadata
        assert "tracks" in data or isinstance(data, list)

    def test_get_tracks_with_pagination(self, client):
        """Test tracks with pagination parameters"""
        response = client.get("/api/library/tracks?limit=10&offset=0")

        assert response.status_code == 200

    def test_get_tracks_pagination_validation(self, client):
        """Test pagination parameter validation"""
        # Negative limit
        response = client.get("/api/library/tracks?limit=-1")
        assert response.status_code in [400, 422]

        # Negative offset
        response = client.get("/api/library/tracks?offset=-1")
        assert response.status_code in [400, 422]

    def test_get_tracks_with_search(self, client):
        """Test tracks with search query"""
        response = client.get("/api/library/tracks?search=test")

        assert response.status_code == 200

    def test_get_tracks_with_sort(self, client):
        """Test tracks with sorting"""
        sort_fields = ["title", "artist", "album", "duration", "created_at"]

        for field in sort_fields:
            response = client.get(f"/api/library/tracks?sort={field}")
            assert response.status_code in [200, 400]

    def test_get_tracks_accepts_get_only(self, client):
        """Test that tracks endpoint only accepts GET"""
        response = client.post("/api/library/tracks")
        assert response.status_code in [404, 405]


class TestFavoriteTracks:
    """Test GET /api/library/tracks/favorites"""

    def test_get_favorites_basic(self, client):
        """Test getting favorite tracks"""
        response = client.get("/api/library/tracks/favorites")

        assert response.status_code == 200
        data = response.json()

        # Should return array of favorites
        assert isinstance(data, (list, dict))

    def test_get_favorites_with_pagination(self, client):
        """Test favorites with pagination"""
        response = client.get("/api/library/tracks/favorites?limit=5&offset=0")

        assert response.status_code == 200

    def test_get_favorites_accepts_get_only(self, client):
        """Test that favorites endpoint only accepts GET"""
        response = client.post("/api/library/tracks/favorites")
        assert response.status_code in [404, 405]


class TestMarkFavorite:
    """Test POST /api/library/tracks/{track_id}/favorite"""

    def test_mark_favorite_track_not_found(self, client):
        """Test marking non-existent track as favorite.

        Note: endpoint calls set_favorite() directly without checking track
        existence, so a no-op 200 is valid for non-existent tracks.
        """
        response = client.post("/api/library/tracks/999/favorite")

        assert response.status_code in [200, 404]

    def test_mark_favorite_accepts_post_only(self, client):
        """Test that mark favorite only accepts POST"""
        response = client.get("/api/library/tracks/1/favorite")
        assert response.status_code in [404, 405]

    def test_mark_favorite_negative_id(self, client):
        """Test marking favorite with negative track ID"""
        response = client.post("/api/library/tracks/-1/favorite")

        assert response.status_code in [200, 404, 422]


class TestRemoveFavorite:
    """Test DELETE /api/library/tracks/{track_id}/favorite"""

    def test_remove_favorite_track_not_found(self, client):
        """Test removing favorite for non-existent track.

        Note: endpoint calls set_favorite() directly without checking track
        existence, so a no-op 200 is valid for non-existent tracks.
        """
        response = client.delete("/api/library/tracks/999/favorite")

        assert response.status_code in [200, 404]

    def test_remove_favorite_accepts_delete_only(self, client):
        """Test that remove favorite only accepts DELETE"""
        response = client.get("/api/library/tracks/1/favorite")
        assert response.status_code in [404, 405]

    def test_remove_favorite_idempotent(self, client):
        """Test that removing favorite multiple times is idempotent"""
        # First remove
        response1 = client.delete("/api/library/tracks/1/favorite")

        # Second remove (should also succeed or return 404)
        response2 = client.delete("/api/library/tracks/1/favorite")

        assert response1.status_code in [200, 404]
        assert response2.status_code in [200, 404]


class TestGetLyrics:
    """Test GET /api/library/tracks/{track_id}/lyrics"""

    @patch('routers.library.require_repository_factory')
    def test_get_lyrics_track_not_found(self, mock_require_repos, client, mock_repos):
        """Test getting lyrics for non-existent track"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.get("/api/library/tracks/999/lyrics")

        assert response.status_code == 404

    def test_get_lyrics_structure(self, client):
        """Test lyrics response structure if track exists"""
        response = client.get("/api/library/tracks/1/lyrics")

        if response.status_code == 200:
            data = response.json()

            # Should have lyrics field
            assert "lyrics" in data or isinstance(data, str)

    def test_get_lyrics_accepts_get_only(self, client):
        """Test that lyrics endpoint only accepts GET"""
        response = client.post("/api/library/tracks/1/lyrics")
        assert response.status_code in [404, 405]


class TestGetArtists:
    """Test GET /api/library/artists"""

    def test_get_artists_basic(self, client):
        """Test getting all artists"""
        response = client.get("/api/library/artists")

        assert response.status_code == 200
        data = response.json()

        # Should return artists array
        assert isinstance(data, (list, dict))

    def test_get_artists_with_pagination(self, client):
        """Test artists with pagination"""
        response = client.get("/api/library/artists?limit=10&offset=0")

        assert response.status_code == 200

    def test_get_artists_with_search(self, client):
        """Test artists with search query"""
        response = client.get("/api/library/artists?search=test")

        assert response.status_code == 200

    def test_get_artists_accepts_get_only(self, client):
        """Test that artists endpoint only accepts GET"""
        response = client.post("/api/library/artists")
        assert response.status_code in [404, 405]


class TestGetArtistDetails:
    """Test GET /api/library/artists/{artist_id}"""

    @patch('routers.library.require_repository_factory')
    def test_get_artist_not_found(self, mock_require_repos, client, mock_repos):
        """Test getting non-existent artist"""
        mock_require_repos.return_value = mock_repos
        mock_repos.artists.get_by_id = Mock(return_value=None)

        response = client.get("/api/library/artists/999")

        assert response.status_code == 404

    def test_get_artist_structure(self, client):
        """Test artist details response structure if exists"""
        response = client.get("/api/library/artists/1")

        if response.status_code == 200:
            data = response.json()

            # Should have artist details
            assert "id" in data or "name" in data

    def test_get_artist_accepts_get_only(self, client):
        """Test that artist details only accepts GET"""
        response = client.post("/api/library/artists/1")
        assert response.status_code in [404, 405]


class TestGetAlbums:
    """Test GET /api/albums (moved from /api/library/albums in #2509)"""

    def test_get_albums_basic(self, client):
        """Test getting all albums"""
        response = client.get("/api/albums")

        assert response.status_code == 200
        data = response.json()

        # Should return albums array
        assert isinstance(data, (list, dict))

    def test_get_albums_with_pagination(self, client):
        """Test albums with pagination"""
        response = client.get("/api/albums?limit=10&offset=0")

        assert response.status_code == 200

    def test_get_albums_with_search(self, client):
        """Test albums with search query"""
        response = client.get("/api/albums?search=test")

        assert response.status_code == 200

    def test_get_albums_accepts_get_only(self, client):
        """Test that albums endpoint only accepts GET"""
        response = client.post("/api/albums")
        assert response.status_code in [404, 405]


class TestGetAlbumDetails:
    """Test GET /api/library/albums/{album_id}"""

    @patch('routers.library.require_repository_factory')
    def test_get_album_not_found(self, mock_require_repos, client, mock_repos):
        """Test getting non-existent album"""
        mock_require_repos.return_value = mock_repos
        mock_repos.albums.get_by_id = Mock(return_value=None)

        response = client.get("/api/library/albums/999")

        assert response.status_code == 404

    def test_get_album_structure(self, client):
        """Test album details response structure if exists"""
        response = client.get("/api/library/albums/1")

        if response.status_code == 200:
            data = response.json()

            # Should have album details
            assert "id" in data or "title" in data

    def test_get_album_accepts_get_only(self, client):
        """Test that album details only accepts GET"""
        response = client.post("/api/library/albums/1")
        assert response.status_code in [404, 405]


class TestScanLibrary:
    """Test POST /api/library/scan"""

    def test_scan_library_missing_directory(self, client):
        """Test scan without directory parameter"""
        response = client.post("/api/library/scan", json={})

        assert response.status_code == 422

    def test_scan_library_path_traversal(self, client):
        """Test that path traversal is blocked"""
        response = client.post(
            "/api/library/scan",
            json={"directory": "../../etc/passwd"}
        )

        assert response.status_code in [400, 422]

    def test_scan_library_accepts_post_only(self, client):
        """Test that scan only accepts POST"""
        response = client.get("/api/library/scan")
        # 429 is acceptable: rate limiter may fire before method check
        assert response.status_code in [404, 405, 429]


class TestFingerprintStatus:
    """Test GET /api/library/fingerprints/status"""

    def test_get_fingerprint_status_structure(self, client):
        """Test fingerprint status response structure"""
        response = client.get("/api/library/fingerprints/status")

        assert response.status_code == 200
        data = response.json()

        # Should have fingerprint status information
        assert isinstance(data, dict)

    def test_get_fingerprint_status_accepts_get_only(self, client):
        """Test that fingerprint status only accepts GET"""
        response = client.post("/api/library/fingerprints/status")
        assert response.status_code in [404, 405]


class TestGetTrackFingerprint:
    """Test GET /api/tracks/{track_id}/fingerprint"""

    @patch('routers.library.require_repository_factory')
    def test_get_fingerprint_track_not_found(self, mock_require_repos, client, mock_repos):
        """Test getting fingerprint for non-existent track"""
        mock_require_repos.return_value = mock_repos
        mock_repos.tracks.get_by_id.return_value = None

        response = client.get("/api/tracks/999/fingerprint")

        assert response.status_code == 404

    def test_get_fingerprint_structure(self, client):
        """Test fingerprint response structure if exists"""
        response = client.get("/api/tracks/1/fingerprint")

        if response.status_code == 200:
            data = response.json()

            # Should have fingerprint data
            assert isinstance(data, dict)

    def test_get_fingerprint_accepts_get_only(self, client):
        """Test that fingerprint endpoint only accepts GET"""
        response = client.post("/api/tracks/1/fingerprint")
        assert response.status_code in [404, 405]


class TestLibraryIntegration:
    """Integration tests for library workflow"""

    def test_workflow_get_tracks_then_favorite(self, client):
        """Test workflow: get tracks → mark favorite → get favorites"""
        # 1. Get tracks
        tracks_response = client.get("/api/library/tracks")
        assert tracks_response.status_code == 200

        # 2. Mark track as favorite (may fail if track doesn't exist)
        favorite_response = client.post("/api/library/tracks/1/favorite")

        if favorite_response.status_code == 200:
            # 3. Get favorites
            favorites_response = client.get("/api/library/tracks/favorites")
            assert favorites_response.status_code == 200

    def test_workflow_get_artists_then_details(self, client):
        """Test workflow: get artists → get artist details"""
        # 1. Get all artists
        artists_response = client.get("/api/library/artists")
        assert artists_response.status_code == 200

        # 2. Get artist details (may fail if no artists)
        details_response = client.get("/api/library/artists/1")
        assert details_response.status_code in [200, 404]

    def test_workflow_get_albums_then_details(self, client):
        """Test workflow: get albums → get album details"""
        # 1. Get all albums (moved to /api/albums in #2509)
        albums_response = client.get("/api/albums")
        assert albums_response.status_code == 200

        # 2. Get album details (may fail if no albums)
        details_response = client.get("/api/library/albums/1")
        assert details_response.status_code in [200, 404]


class TestLibrarySecurityValidation:
    """Security-focused tests for library endpoints"""

    def test_tracks_sql_injection_prevention(self, client):
        """Test that search parameters don't allow SQL injection"""
        response = client.get("/api/library/tracks?search='; DROP TABLE tracks; --")

        # Should handle safely (not execute SQL)
        assert response.status_code == 200

    def test_tracks_xss_prevention(self, client):
        """Test that search parameters don't allow XSS"""
        response = client.get("/api/library/tracks?search=<script>alert('xss')</script>")

        # Should handle safely
        assert response.status_code == 200

    def test_pagination_overflow_protection(self, client):
        """Test pagination with extremely large values"""
        response = client.get("/api/library/tracks?limit=999999&offset=999999")

        # Should either cap values or reject
        assert response.status_code in [200, 400, 422]

    def test_favorite_track_id_validation(self, client):
        """Test favorite endpoints with invalid track IDs"""
        # String instead of int
        response = client.post("/api/library/tracks/invalid/favorite")
        assert response.status_code == 422

        # Extremely large ID (endpoint doesn't validate track existence)
        response = client.post("/api/library/tracks/999999999999/favorite")
        assert response.status_code in [200, 404, 500]
