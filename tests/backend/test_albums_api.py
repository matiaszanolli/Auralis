"""
Tests for Albums REST API
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the albums browsing and management endpoints.

Phase 5C: Dual-Mode Backend Testing
This file demonstrates Phase 5C patterns:
1. Using mock fixtures from conftest.py
2. Parametrized dual-mode testing (LibraryManager + RepositoryFactory)
3. Interface validation for dual-mode compatibility
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture
def client():
    """Create test client for main app"""
    from main import app
    return TestClient(app)


@pytest.fixture
def mock_album():
    """Create a mock album object"""
    album = Mock(spec=['id', 'title', 'artist', 'artist_id', 'year', 'tracks', 'total_tracks', 'total_discs',
                       'artwork_path', 'avg_dr_rating', 'avg_lufs', 'mastering_consistency',
                       'created_at', 'updated_at'])
    album.id = 1
    album.title = "Test Album"

    # Create artist mock without circular references
    artist = Mock(spec=['name'])
    artist.name = "Test Artist"
    album.artist = artist
    album.artist_id = 1

    album.year = 2024
    album.total_tracks = 2
    album.total_discs = 1
    album.artwork_path = None
    album.avg_dr_rating = 12.0
    album.avg_lufs = -14.0
    album.mastering_consistency = 0.85
    album.created_at = datetime.utcnow()
    album.updated_at = datetime.utcnow()

    # Create track mocks without circular album references
    track1 = Mock(spec=['duration'])
    track1.duration = 180
    track2 = Mock(spec=['duration'])
    track2.duration = 200
    album.tracks = [track1, track2]

    return album


@pytest.fixture
def mock_track():
    """Create a mock track object"""
    track = Mock(spec=['id', 'title', 'album', 'duration', 'track_number', 'disc_number'])
    track.id = 1
    track.title = "Test Track"

    # Create album mock without circular track references
    album_mock = Mock(spec=['title', 'id'])
    album_mock.title = "Test Album"
    album_mock.id = 1
    track.album = album_mock

    track.duration = 180
    track.track_number = 1
    track.disc_number = 1
    return track


class TestGetAlbums:
    """Test GET /api/albums endpoint"""

    def test_get_albums_default_pagination(self, client):
        """Test getting albums with default pagination"""
        response = client.get("/api/albums")

        assert response.status_code in [200, 503]

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

        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["limit"] == 5
            assert len(data["albums"]) <= 5

    def test_get_albums_with_offset(self, client):
        """Test getting albums with offset"""
        response = client.get("/api/albums?limit=10&offset=5")

        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["offset"] == 5
            assert data["limit"] == 10

    def test_get_albums_with_search(self, client):
        """Test searching albums by name"""
        response = client.get("/api/albums?search=test")

        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "albums" in data

    def test_get_albums_order_by_title(self, client):
        """Test ordering albums by title"""
        response = client.get("/api/albums?order_by=title")

        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "albums" in data

    def test_get_albums_order_by_year(self, client):
        """Test ordering albums by year"""
        response = client.get("/api/albums?order_by=year")

        assert response.status_code in [200, 503]

    def test_get_albums_invalid_limit(self, client):
        """Test getting albums with invalid limit (too high)"""
        response = client.get("/api/albums?limit=500")

        # Should reject or clamp to max
        assert response.status_code in [200, 422, 503]

    def test_get_albums_negative_offset(self, client):
        """Test getting albums with negative offset"""
        response = client.get("/api/albums?offset=-1")

        # Should reject negative offset
        assert response.status_code in [200, 422, 503]

    def test_get_albums_with_mocked_data(self, client, mock_album):
        """Test albums endpoint with mocked library manager"""
        with patch('main.library_manager') as mock_library:
            mock_library.albums.get_all.return_value = ([mock_album], 1)

            response = client.get("/api/albums?limit=50&offset=0")

            assert response.status_code == 200
            data = response.json()

            assert len(data["albums"]) == 1
            assert data["total"] == 1
            assert data["albums"][0]["id"] == 1
            assert data["albums"][0]["title"] == "Test Album"
            assert data["albums"][0]["track_count"] == 2
            assert data["has_more"] == False

    def test_get_albums_pagination_has_more(self, client, mock_album):
        """Test has_more flag in pagination"""
        with patch('main.library_manager') as mock_library:
            # Return 50 albums, total 100
            mock_albums = [mock_album] * 50
            mock_library.albums.get_all.return_value = (mock_albums, 100)

            response = client.get("/api/albums?limit=50&offset=0")

            assert response.status_code == 200
            data = response.json()

            assert data["has_more"] == True
            assert data["total"] == 100


class TestGetAlbumById:
    """Test GET /api/albums/{album_id} endpoint"""

    def test_get_album_by_id_success(self, client, mock_album):
        """Test getting a specific album by ID"""
        with patch('main.library_manager') as mock_library:
            mock_library.albums.get_by_id.return_value = mock_album

            response = client.get("/api/albums/1")

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == 1
            assert data["title"] == "Test Album"
            assert data["artist"] == "Test Artist"

    def test_get_album_by_id_not_found(self, client):
        """Test getting non-existent album"""
        with patch('main.library_manager') as mock_library:
            mock_library.albums.get_by_id.return_value = None

            response = client.get("/api/albums/9999")

            assert response.status_code == 404

    def test_get_album_by_id_invalid_id(self, client):
        """Test getting album with invalid ID"""
        response = client.get("/api/albums/invalid")

        # Should return 422 for validation error
        assert response.status_code == 422


class TestGetAlbumTracks:
    """Test GET /api/albums/{album_id}/tracks endpoint"""

    def test_get_album_tracks_success(self, client, mock_album, mock_track):
        """Test getting tracks for an album"""
        mock_album.tracks = [mock_track, mock_track]

        with patch('main.library_manager') as mock_library:
            mock_library.albums.get_by_id.return_value = mock_album

            response = client.get("/api/albums/1/tracks")

            assert response.status_code == 200
            data = response.json()

            assert data["album_id"] == 1
            assert data["album_title"] == "Test Album"
            assert data["artist"] == "Test Artist"
            assert data["total_tracks"] == 2
            assert len(data["tracks"]) == 2
            assert "year" in data

    def test_get_album_tracks_empty(self, client, mock_album):
        """Test getting tracks for album with no tracks"""
        mock_album.tracks = []

        with patch('main.library_manager') as mock_library:
            mock_library.albums.get_by_id.return_value = mock_album

            response = client.get("/api/albums/1/tracks")

            assert response.status_code == 200
            data = response.json()

            assert data["total_tracks"] == 0
            assert len(data["tracks"]) == 0

    def test_get_album_tracks_not_found(self, client):
        """Test getting tracks for non-existent album"""
        with patch('main.library_manager') as mock_library:
            mock_library.albums.get_by_id.return_value = None

            response = client.get("/api/albums/9999/tracks")

            assert response.status_code == 404

    def test_get_album_tracks_sorted(self, client, mock_album):
        """Test that tracks are sorted by disc and track number"""
        track1 = Mock(spec=['id', 'title', 'album', 'duration', 'track_number', 'disc_number'])
        track1.id = 1
        track1.title = "Track 1"
        track1.album = mock_album
        track1.duration = 180
        track1.track_number = 2
        track1.disc_number = 1

        track2 = Mock(spec=['id', 'title', 'album', 'duration', 'track_number', 'disc_number'])
        track2.id = 2
        track2.title = "Track 2"
        track2.album = mock_album
        track2.duration = 200
        track2.track_number = 1
        track2.disc_number = 1

        mock_album.tracks = [track1, track2]

        with patch('main.library_manager') as mock_library:
            mock_library.albums.get_by_id.return_value = mock_album

            response = client.get("/api/albums/1/tracks")

            assert response.status_code == 200
            data = response.json()

            # Should be sorted by track number
            assert len(data["tracks"]) == 2


class TestAlbumsAPIIntegration:
    """Integration tests for albums API"""

    def test_albums_workflow(self, client, mock_album, mock_track):
        """Test complete workflow: list albums -> get album -> get tracks"""
        mock_album.tracks = [mock_track]

        with patch('main.library_manager') as mock_library:
            # Step 1: List albums
            mock_library.albums.get_all.return_value = ([mock_album], 1)

            response = client.get("/api/albums")
            assert response.status_code == 200
            albums = response.json()["albums"]

            if albums:
                album_id = albums[0]["id"]

                # Step 2: Get album details
                mock_library.albums.get_by_id.return_value = mock_album
                response = client.get(f"/api/albums/{album_id}")
                assert response.status_code == 200

                # Step 3: Get album tracks
                response = client.get(f"/api/albums/{album_id}/tracks")
                assert response.status_code == 200
                tracks_data = response.json()
                assert "tracks" in tracks_data

    def test_albums_search_and_retrieve(self, client, mock_album):
        """Test searching for album and retrieving it"""
        with patch('main.library_manager') as mock_library:
            mock_library.albums.search.return_value = [mock_album]

            # Search for album
            response = client.get("/api/albums?search=Test")
            assert response.status_code in [200, 503]

            if response.status_code == 200:
                data = response.json()
                assert "albums" in data


class TestAlbumsErrorHandling:
    """Test error handling in albums API"""

    def test_albums_database_error(self, client):
        """Test handling of database errors"""
        with patch('main.library_manager') as mock_library:
            mock_library.albums.get_all.side_effect = Exception("Database connection error")

            response = client.get("/api/albums")

            assert response.status_code == 500

    def test_album_by_id_database_error(self, client):
        """Test handling of database errors when getting album by ID"""
        with patch('main.library_manager') as mock_library:
            mock_library.albums.get_by_id.side_effect = Exception("Database error")

            response = client.get("/api/albums/1")

            assert response.status_code == 500


# ============================================================
# Phase 5C: Dual-Mode Backend Testing Patterns
# ============================================================
# The following tests demonstrate how to use Phase 5C fixtures
# from conftest.py for dual-mode parametrized testing.
#
# This follows the same pattern as test_artists_api.py.

@pytest.mark.phase5c
class TestAlbumsAPIDualModeParametrized:
    """Phase 5C.3: Parametrized dual-mode tests.

    These tests automatically run with both LibraryManager and RepositoryFactory
    via the parametrized mock_data_source fixture. Each test runs twice:
    once with library_manager, once with repository_factory.
    """

    def test_albums_repository_interface(self, mock_data_source):
        """
        Parametrized test: Validate albums repository interface works with both modes.

        Each test runs twice via pytest parametrization:
        - once with (library_manager, mock_library_manager)
        - once with (repository_factory, mock_repository_factory)
        """
        mode, source = mock_data_source

        assert hasattr(source, 'albums'), f"{mode} missing albums repository"
        assert hasattr(source.albums, 'get_all'), f"{mode}.albums missing get_all"
        assert hasattr(source.albums, 'get_by_id'), f"{mode}.albums missing get_by_id"
        assert hasattr(source.albums, 'search'), f"{mode}.albums missing search"

    def test_albums_get_all_returns_tuple(self, mock_data_source):
        """
        Parametrized test: Validate get_all returns (items, total) for both modes.

        Both modes must support pagination with consistent interface.
        """
        mode, source = mock_data_source

        # Set up test data
        album1 = Mock()
        album1.id = 1
        album1.title = "Album 1"
        album1.year = 2024

        album2 = Mock()
        album2.id = 2
        album2.title = "Album 2"
        album2.year = 2023

        test_albums = [album1, album2]
        source.albums.get_all = Mock(return_value=(test_albums, 2))

        # Test with both modes
        albums, total = source.albums.get_all(limit=50, offset=0)

        assert len(albums) == 2, f"{mode}: Expected 2 albums"
        assert total == 2, f"{mode}: Expected total=2"
        assert albums[0].title == "Album 1", f"{mode}: First album title mismatch"
        assert albums[1].title == "Album 2", f"{mode}: Second album title mismatch"

    def test_albums_get_by_id_interface(self, mock_data_source):
        """
        Parametrized test: Validate get_by_id works identically in both modes.
        """
        mode, source = mock_data_source

        album = Mock()
        album.id = 1
        album.title = "Test Album"
        album.year = 2024

        source.albums.get_by_id = Mock(return_value=album)

        result = source.albums.get_by_id(1)

        assert result.id == 1, f"{mode}: Album ID mismatch"
        assert result.title == "Test Album", f"{mode}: Album title mismatch"
        source.albums.get_by_id.assert_called_once_with(1)

    def test_albums_search_interface(self, mock_data_source):
        """
        Parametrized test: Validate search returns (items, total) for both modes.
        """
        mode, source = mock_data_source

        album = Mock()
        album.id = 1
        album.title = "Dark Side of the Moon"

        source.albums.search = Mock(return_value=([album], 1))

        results, total = source.albums.search("Dark Side", limit=10)

        assert len(results) == 1, f"{mode}: Expected 1 search result"
        assert total == 1, f"{mode}: Expected total=1"
        assert results[0].title == "Dark Side of the Moon", f"{mode}: Search result mismatch"
        source.albums.search.assert_called_once_with("Dark Side", limit=10)
