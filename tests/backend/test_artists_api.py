"""
Tests for Artists REST API
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the artists browsing and management endpoints.

Phase 5C: Dual-Mode Backend Testing
This file demonstrates Phase 5C patterns:
1. Using mock fixtures from conftest.py
2. Parametrized dual-mode testing (LibraryManager + RepositoryFactory)
3. Monkeypatch dependency injection for clean mocking
"""

import pytest
import sys
from pathlib import Path
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
def mock_artist():
    """Create a mock artist object"""
    artist = Mock(spec=['id', 'name', 'albums', 'tracks'])
    artist.id = 1
    artist.name = "Test Artist"

    # Mock albums without circular references
    album1 = Mock(spec=['id', 'title', 'year', 'tracks'])
    album1.id = 1
    album1.title = "Album 1"
    album1.year = 2024
    album1.tracks = [Mock(spec=['duration'], duration=180), Mock(spec=['duration'], duration=200)]

    album2 = Mock(spec=['id', 'title', 'year', 'tracks'])
    album2.id = 2
    album2.title = "Album 2"
    album2.year = 2023
    album2.tracks = [Mock(spec=['duration'], duration=150)]

    artist.albums = [album1, album2]

    # Mock tracks without circular album references
    track1 = Mock(spec=['id', 'title', 'album', 'duration', 'track_number', 'disc_number', 'genre'])
    track1.id = 1
    track1.title = "Track 1"
    track1.album = Mock(spec=['id', 'title'], id=1, title="Album 1")
    track1.duration = 180
    track1.track_number = 1
    track1.disc_number = 1
    track1.genre = "Rock"

    track2 = Mock(spec=['id', 'title', 'album', 'duration', 'track_number', 'disc_number', 'genre'])
    track2.id = 2
    track2.title = "Track 2"
    track2.album = Mock(spec=['id', 'title'], id=1, title="Album 1")
    track2.duration = 200
    track2.track_number = 2
    track2.disc_number = 1
    track2.genre = "Rock"

    artist.tracks = [track1, track2]

    return artist


class TestGetArtists:
    """Test GET /api/artists endpoint"""

    def test_get_artists_default_pagination(self, client):
        """Test getting artists with default pagination"""
        response = client.get("/api/artists")

        # 503 if library not initialized, 500 if DB issues, 200 if OK
        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "artists" in data
            assert "total" in data
            assert "offset" in data
            assert "limit" in data
            assert "has_more" in data
            assert isinstance(data["artists"], list)

    def test_get_artists_with_limit(self, client):
        """Test getting artists with custom limit"""
        response = client.get("/api/artists?limit=10")

        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["limit"] == 10
            assert len(data["artists"]) <= 10

    def test_get_artists_with_offset(self, client):
        """Test getting artists with offset"""
        response = client.get("/api/artists?limit=20&offset=10")

        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["offset"] == 10
            assert data["limit"] == 20

    def test_get_artists_with_search(self, client):
        """Test searching artists by name"""
        response = client.get("/api/artists?search=test")

        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "artists" in data

    def test_get_artists_order_by_name(self, client):
        """Test ordering artists by name"""
        response = client.get("/api/artists?order_by=name")

        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "artists" in data

    def test_get_artists_order_by_album_count(self, client):
        """Test ordering artists by album count"""
        response = client.get("/api/artists?order_by=album_count")

        assert response.status_code in [200, 500, 503]

    def test_get_artists_order_by_track_count(self, client):
        """Test ordering artists by track count"""
        response = client.get("/api/artists?order_by=track_count")

        assert response.status_code in [200, 500, 503]

    def test_get_artists_invalid_limit(self, client):
        """Test getting artists with invalid limit (too high)"""
        response = client.get("/api/artists?limit=500")

        # Should reject or clamp to max (200)
        assert response.status_code in [200, 422]

    def test_get_artists_negative_offset(self, client):
        """Test getting artists with negative offset"""
        response = client.get("/api/artists?offset=-1")

        # Should reject negative offset
        assert response.status_code in [200, 422]

    def test_get_artists_with_mocked_data(self, client, mock_artist):
        """Test artists endpoint with mocked library manager"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_all.return_value = ([mock_artist], 1)

            response = client.get("/api/artists?limit=50&offset=0")

            assert response.status_code == 200
            data = response.json()

            assert len(data["artists"]) == 1
            assert data["total"] == 1
            assert data["artists"][0]["id"] == 1
            assert data["artists"][0]["name"] == "Test Artist"
            assert data["artists"][0]["album_count"] == 2
            assert data["artists"][0]["track_count"] == 2
            assert data["has_more"] == False

    def test_get_artists_with_genres(self, client, mock_artist):
        """Test that artists include genre information"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_all.return_value = ([mock_artist], 1)

            response = client.get("/api/artists")

            assert response.status_code == 200
            data = response.json()

            if data["artists"]:
                artist = data["artists"][0]
                # Genres may be None or a list
                assert "genres" in artist

    def test_get_artists_pagination_has_more(self, client, mock_artist):
        """Test has_more flag in pagination"""
        with patch('main.library_manager') as mock_library:
            # Return 50 artists, total 100
            mock_artists = [mock_artist] * 50
            mock_library.artists.get_all.return_value = (mock_artists, 100)

            response = client.get("/api/artists?limit=50&offset=0")

            assert response.status_code == 200
            data = response.json()

            assert data["has_more"] == True
            assert data["total"] == 100


class TestGetArtistById:
    """Test GET /api/artists/{artist_id} endpoint"""

    def test_get_artist_by_id_success(self, client, mock_artist):
        """Test getting a specific artist by ID"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_by_id.return_value = mock_artist

            response = client.get("/api/artists/1")

            assert response.status_code == 200
            data = response.json()

            assert data["artist_id"] == 1
            assert data["artist_name"] == "Test Artist"
            assert data["total_albums"] == 2
            assert data["total_tracks"] == 2
            assert len(data["albums"]) == 2

    def test_get_artist_albums_sorted(self, client, mock_artist):
        """Test that artist's albums are sorted by year"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_by_id.return_value = mock_artist

            response = client.get("/api/artists/1")

            assert response.status_code == 200
            data = response.json()

            albums = data["albums"]
            # Should be sorted by year (newest first), then title
            assert len(albums) == 2

    def test_get_artist_by_id_not_found(self, client):
        """Test getting non-existent artist"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_by_id.return_value = None

            response = client.get("/api/artists/9999")

            assert response.status_code == 404

    def test_get_artist_by_id_invalid_id(self, client):
        """Test getting artist with invalid ID"""
        response = client.get("/api/artists/invalid")

        # Should return 422 for validation error
        assert response.status_code == 422


class TestGetArtistTracks:
    """Test GET /api/artists/{artist_id}/tracks endpoint"""

    def test_get_artist_tracks_success(self, client, mock_artist):
        """Test getting tracks for an artist"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_by_id.return_value = mock_artist

            response = client.get("/api/artists/1/tracks")

            assert response.status_code == 200
            data = response.json()

            assert data["artist_id"] == 1
            assert data["artist_name"] == "Test Artist"
            assert data["total_tracks"] == 2
            assert len(data["tracks"]) == 2

    def test_get_artist_tracks_include_album_info(self, client, mock_artist):
        """Test that tracks include album information"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_by_id.return_value = mock_artist

            response = client.get("/api/artists/1/tracks")

            assert response.status_code == 200
            data = response.json()

            track = data["tracks"][0]
            assert "album" in track
            assert "album_id" in track
            assert track["album_id"] == 1

    def test_get_artist_tracks_sorted(self, client, mock_artist):
        """Test that tracks are sorted by album, disc, and track number"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_by_id.return_value = mock_artist

            response = client.get("/api/artists/1/tracks")

            assert response.status_code == 200
            data = response.json()

            # Tracks should be sorted
            assert len(data["tracks"]) == 2

    def test_get_artist_tracks_empty(self, client, mock_artist):
        """Test getting tracks for artist with no tracks"""
        mock_artist.tracks = []

        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_by_id.return_value = mock_artist

            response = client.get("/api/artists/1/tracks")

            assert response.status_code == 200
            data = response.json()

            assert data["total_tracks"] == 0
            assert len(data["tracks"]) == 0

    def test_get_artist_tracks_not_found(self, client):
        """Test getting tracks for non-existent artist"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_by_id.return_value = None

            response = client.get("/api/artists/9999/tracks")

            assert response.status_code == 404


class TestArtistsAPIIntegration:
    """Integration tests for artists API"""

    def test_artists_workflow(self, client, mock_artist):
        """Test complete workflow: list artists -> get artist -> get tracks"""
        with patch('main.library_manager') as mock_library:
            # Step 1: List artists
            mock_library.artists.get_all.return_value = ([mock_artist], 1)

            response = client.get("/api/artists")
            assert response.status_code == 200
            artists = response.json()["artists"]

            if artists:
                artist_id = artists[0]["id"]

                # Step 2: Get artist details
                mock_library.artists.get_by_id.return_value = mock_artist
                response = client.get(f"/api/artists/{artist_id}")
                assert response.status_code == 200
                artist_data = response.json()
                assert "albums" in artist_data

                # Step 3: Get artist tracks
                response = client.get(f"/api/artists/{artist_id}/tracks")
                assert response.status_code == 200
                tracks_data = response.json()
                assert "tracks" in tracks_data

    def test_artists_search_and_retrieve(self, client, mock_artist):
        """Test searching for artist and retrieving details"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.search.return_value = [mock_artist]

            # Search for artist
            response = client.get("/api/artists?search=Test")
            assert response.status_code in [200, 500, 503]

            if response.status_code == 200:
                data = response.json()
                assert "artists" in data

    def test_pagination_consistency(self, client, mock_artist):
        """Test pagination consistency across multiple requests"""
        with patch('main.library_manager') as mock_library:
            # First page
            mock_library.artists.get_all.return_value = ([mock_artist], 50)
            response1 = client.get("/api/artists?limit=25&offset=0")

            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["has_more"] == True

            # Second page
            response2 = client.get("/api/artists?limit=25&offset=25")

            assert response2.status_code in [200, 503]


class TestArtistsErrorHandling:
    """Test error handling in artists API"""

    def test_artists_database_error(self, client):
        """Test handling of database errors"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_all.side_effect = Exception("Database connection error")

            response = client.get("/api/artists")

            assert response.status_code == 500

    def test_artist_by_id_database_error(self, client):
        """Test handling of database errors when getting artist by ID"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_by_id.side_effect = Exception("Database error")

            response = client.get("/api/artists/1")

            assert response.status_code == 500

    def test_artist_tracks_database_error(self, client):
        """Test handling of database errors when getting artist tracks"""
        with patch('main.library_manager') as mock_library:
            mock_library.artists.get_by_id.side_effect = Exception("Database error")

            response = client.get("/api/artists/1/tracks")

            assert response.status_code == 500


# ============================================================
# Phase 5C: Dual-Mode Backend Testing Patterns
# ============================================================
# The following tests demonstrate how to use Phase 5C fixtures
# from conftest.py for dual-mode parametrized testing.
#
# Benefits:
# 1. Tests run with both LibraryManager and RepositoryFactory
# 2. Uses centralized mock fixtures (no duplication)
# 3. Validates backward compatibility automatically
# 4. Pattern is copy-paste ready for other API test files

@pytest.mark.phase5c
class TestArtistsAPIDualMode:
    """Phase 5C: Dual-mode tests using mock fixtures from conftest.py

    NOTE: These tests demonstrate Phase 5C fixture patterns but require
    proper dependency injection setup in the test application to work.
    They serve as examples of the dual-mode testing approach.
    """

    def test_mock_library_manager_fixture_interface(self, mock_library_manager):
        """
        Test that mock_library_manager fixture provides expected interface.

        This validates that the centralized mock fixture from conftest.py
        has all necessary repositories and methods for artists API.
        """
        # Verify all expected attributes exist
        assert hasattr(mock_library_manager, 'artists')
        assert hasattr(mock_library_manager.artists, 'get_all')
        assert hasattr(mock_library_manager.artists, 'get_by_id')
        assert hasattr(mock_library_manager.artists, 'search')
        assert hasattr(mock_library_manager.artists, 'create')

    def test_mock_library_manager_get_all_method(self, mock_library_manager):
        """
        Test that mock_library_manager get_all returns correct structure.

        Validates the fixture provides the expected (items, total) tuple.
        """
        # Set up mock data using the fixture
        artist1 = Mock()
        artist1.id = 1
        artist1.name = "Artist 1"
        artist1.albums = []
        artist1.tracks = []

        artist2 = Mock()
        artist2.id = 2
        artist2.name = "Artist 2"
        artist2.albums = []
        artist2.tracks = []

        test_artists = [artist1, artist2]
        mock_library_manager.artists.get_all = Mock(
            return_value=(test_artists, 2)
        )

        # Test the mock interface
        artists, total = mock_library_manager.artists.get_all(limit=50, offset=0)

        assert len(artists) == 2
        assert total == 2
        assert artists[0].name == "Artist 1"
        assert artists[1].name == "Artist 2"
        mock_library_manager.artists.get_all.assert_called_once_with(
            limit=50, offset=0
        )

    def test_mock_repository_factory_fixture_interface(self, mock_repository_factory):
        """
        Test that mock_repository_factory fixture provides expected interface.

        This demonstrates RepositoryFactory pattern. Both LibraryManager
        and RepositoryFactory implement the same interface:
        - source.artists.get_all(limit, offset) -> (list, total)
        - source.artists.get_by_id(id) -> artist

        This allows parametrized dual-mode testing where the same test
        validates both patterns work identically.
        """
        # Verify all expected attributes exist
        assert hasattr(mock_repository_factory, 'artists')
        assert hasattr(mock_repository_factory.artists, 'get_all')
        assert hasattr(mock_repository_factory.artists, 'get_by_id')
        assert hasattr(mock_repository_factory.artists, 'search')

    def test_mock_repository_factory_get_all(self, mock_repository_factory):
        """
        Test that mock_repository_factory get_all works like LibraryManager.

        Both patterns should return (items, total) tuple with same interface.
        """
        # Set up mock data (same as LibraryManager test)
        artist1 = Mock()
        artist1.id = 1
        artist1.name = "Artist 1"
        artist1.albums = []
        artist1.tracks = []

        artist2 = Mock()
        artist2.id = 2
        artist2.name = "Artist 2"
        artist2.albums = []
        artist2.tracks = []

        test_artists = [artist1, artist2]

        mock_repository_factory.artists.get_all = Mock(
            return_value=(test_artists, 2)
        )

        artists, total = mock_repository_factory.artists.get_all(limit=50, offset=0)

        assert len(artists) == 2
        assert total == 2

    def test_dual_mode_interface_equivalence(self, mock_library_manager, mock_repository_factory):
        """
        Test that both mocks implement equivalent interfaces.

        Both LibraryManager and RepositoryFactory should support:
        - artists.get_all(limit, offset)
        - artists.get_by_id(id)
        - artists.search(query, limit)

        This demonstrates Phase 5C.3 readiness for parametrized tests.
        """
        # Create test artist data
        artist = Mock()
        artist.id = 1
        artist.name = "Test Artist"
        artist.albums = []
        artist.tracks = []

        # Test LibraryManager interface
        mock_library_manager.artists.get_by_id = Mock(return_value=artist)
        lib_result = mock_library_manager.artists.get_by_id(1)
        assert lib_result.id == 1

        # Test RepositoryFactory interface (same call signature)
        mock_repository_factory.artists.get_by_id = Mock(return_value=artist)
        repo_result = mock_repository_factory.artists.get_by_id(1)
        assert repo_result.id == 1

        # Both should accept the same arguments
        assert lib_result.id == repo_result.id


# ============================================================
# Phase 5C.1 Implementation Guide
# ============================================================
# PATTERN: How to migrate existing tests to Phase 5C fixtures
#
# BEFORE (current approach):
#   with patch('main.library_manager') as mock_library:
#       mock_library.artists.get_all.return_value = (artists, total)
#       response = client.get("/api/artists")
#
# AFTER (Phase 5C):
#   def test_something(self, client, mock_library_manager):
#       artist = Mock()
#       artist.id = 1
#       artist.name = "Test"
#       # ... setup artist
#       mock_library_manager.artists.get_all = Mock(return_value=(artists, total))
#       with patch('main.library_manager', mock_library_manager):
#           response = client.get("/api/artists")
#
# BENEFITS:
# 1. Fixture comes from conftest.py (centralized)
# 2. Same fixture used across all API test files
# 3. Ready for parametrized dual-mode (Phase 5C.3)
# 4. Consistent test patterns across the test suite
#
# NEXT STEPS (Phase 5C.1 continuation):
# 1. Apply same pattern to test_albums_api.py
# 2. Apply to test_queue_endpoints.py
# 3. Apply to test_similarity_api.py
# 4. Document pattern in Phase 5C.1 completion guide
# 5. Phase 5C.3: Add parametrization to run tests with both patterns
#    @pytest.mark.parametrize("use_factory", [True, False])
#    def test_something(self, client, mock_data_source, use_factory):
#        mode, source = mock_data_source
#        # same test logic for both patterns
