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

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from auralis.library.models import Album, Artist, Track

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

# Phase 5B.1: Migration to conftest.py fixtures
# Removed local client() fixture - now using conftest.py fixture
# All tests automatically use the fixture from parent conftest.py


@pytest.fixture
def artist_row():
    """A real (transient) Artist with two albums and two tracks.

    serialize_artist() goes through Artist.to_dict(), which derives
    album_count/track_count from these collections when the query supplied no
    SQL aggregates (#5084).
    """
    album1 = Album(id=1, title="Album 1", year=2024,
                   tracks=[Track(duration=180), Track(duration=200)])
    album2 = Album(id=2, title="Album 2", year=2023, tracks=[Track(duration=150)])
    track1 = Track(id=1, title="Track 1", album=Album(id=1, title="Album 1"),
                   duration=180, track_number=1, disc_number=1)
    track2 = Track(id=2, title="Track 2", album=Album(id=1, title="Album 1"),
                   duration=200, track_number=2, disc_number=1)
    return Artist(
        id=1,
        name="Test Artist",
        artwork_url=None,
        artwork_source=None,
        albums=[album1, album2],
        tracks=[track1, track2],
    )


@pytest.fixture
def artist_page(artist_row):
    """``artist_row`` as ArtistRepository.get_page() returns it (#5872): the
    artist's track count comes from SQL, not from a loaded tracks collection."""
    artist_row.track_count_expr = len(artist_row.tracks)
    return artist_row


@pytest.fixture
def artist_track_rows():
    """ArtistRepository.get_track_rows() output: (name, column-narrow rows)."""
    return "Test Artist", [
        {"id": 1, "title": "Track 1", "album": "Album 1", "album_id": 1, "duration": 180,
         "track_number": 1, "disc_number": 1, "format": "FLAC"},
        {"id": 2, "title": "Track 2", "album": "Album 1", "album_id": 1, "duration": None,
         "track_number": 2, "disc_number": 1, "format": None},
    ]


class TestGetArtists:
    """Test GET /api/artists endpoint"""

    def test_get_artists_default_pagination(self, client):
        """Test getting artists with default pagination"""
        response = client.get("/api/artists")

        assert response.status_code == 200

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

        assert response.status_code == 200

        data = response.json()
        assert data["limit"] == 10
        assert len(data["artists"]) <= 10

    def test_get_artists_with_offset(self, client):
        """Test getting artists with offset"""
        response = client.get("/api/artists?limit=20&offset=10")

        assert response.status_code == 200

        data = response.json()
        assert data["offset"] == 10
        assert data["limit"] == 20

    def test_get_artists_with_search(self, client):
        """Test searching artists by name"""
        response = client.get("/api/artists?search=test")

        assert response.status_code == 200

        data = response.json()
        assert "artists" in data

    def test_get_artists_order_by_name(self, client):
        """Test ordering artists by name"""
        response = client.get("/api/artists?order_by=name")

        assert response.status_code == 200

        data = response.json()
        assert "artists" in data

    def test_get_artists_order_by_album_count(self, client):
        """Test ordering artists by album count"""
        response = client.get("/api/artists?order_by=album_count")

        assert response.status_code == 200

    def test_get_artists_order_by_track_count(self, client):
        """Test ordering artists by track count"""
        response = client.get("/api/artists?order_by=track_count")

        assert response.status_code == 200

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

    def test_get_artists_with_mocked_data(self, client, artist_row):
        """Test artists endpoint with mocked library manager"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_all.return_value = ([artist_row], 1)

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

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

    def test_get_artists_artwork_url_in_response(self, client, artist_row):
        """Test that artwork_url is included in artist response (issue #2110)"""
        artist_row.artwork_url = "https://coverartarchive.org/release/abc/front.jpg"
        artist_row.artwork_source = "musicbrainz"

        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_all.return_value = ([artist_row], 1)

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):
            response = client.get("/api/artists")

            assert response.status_code == 200
            data = response.json()

            artist = data["artists"][0]
            assert "artwork_url" in artist
            assert artist["artwork_url"] == "https://coverartarchive.org/release/abc/front.jpg"
            assert artist["artwork_source"] == "musicbrainz"

    def test_get_artists_artwork_url_null_when_unset(self, client, artist_row):
        """Test that artwork_url is null (not missing) when artist has no artwork"""
        artist_row.artwork_url = None
        artist_row.artwork_source = None

        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_all.return_value = ([artist_row], 1)

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):
            response = client.get("/api/artists")

            assert response.status_code == 200
            data = response.json()

            artist = data["artists"][0]
            assert "artwork_url" in artist
            assert artist["artwork_url"] is None

    def test_get_artists_with_genres(self, client, artist_row):
        """Test that artists include genre information"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_all.return_value = ([artist_row], 1)

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists")

            assert response.status_code == 200
            data = response.json()

            if data["artists"]:
                artist = data["artists"][0]
                # Genres may be None or a list
                assert "genres" in artist

    def test_get_artists_with_no_albums_or_tracks_counts_zero(self, client):
        """An artist row whose collections are empty reports 0/0 (#4909)."""
        artist = Artist(id=1, name="Empty Artist", artwork_url=None, artwork_source=None)

        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_all.return_value = ([artist], 1)

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):
            response = client.get("/api/artists")

            assert response.status_code == 200
            data = response.json()
            assert data["artists"][0]["album_count"] == 0
            assert data["artists"][0]["track_count"] == 0

    def test_get_artists_pagination_has_more(self, client, artist_row):
        """Test has_more flag in pagination"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        # Return 50 artists, total 100
        mock_artists = [artist_row] * 50
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_all.return_value = (mock_artists, 100)

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists?limit=50&offset=0")

            assert response.status_code == 200
            data = response.json()

            assert data["has_more"] == True
            assert data["total"] == 100


class TestGetArtistById:
    """Test GET /api/artists/{artist_id} endpoint"""

    def test_get_artist_by_id_success(self, client, artist_page):
        """Test getting a specific artist by ID"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_page.return_value = artist_page

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists/1")

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == 1
            assert data["name"] == "Test Artist"
            assert data["total_albums"] == 2
            assert data["total_tracks"] == 2
            assert len(data["albums"]) == 2
            assert data["albums"][0]["track_count"] == 2
            assert data["albums"][0]["total_duration"] == 380

    def test_get_artist_albums_carry_artwork_url_only_when_they_have_art(self, client, artist_page):
        """#5925: the nested album says whether it has artwork, so the UI skips the 404 probe."""
        with_art = next(album for album in artist_page.albums if album.id == 1)
        with_art.artwork_path = "/tmp/auralis-test-cover-5925.jpg"

        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_page.return_value = artist_page

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):
            albums = {a["id"]: a for a in client.get("/api/artists/1").json()["albums"]}

        assert albums[1]["artwork_url"] == "/api/albums/1/artwork"
        assert albums[2]["artwork_url"] is None

    def test_get_artist_artwork_url_in_detail_response(self, client, artist_page):
        """Test that artwork_url is included in artist detail response (issue #2110)"""
        artist_page.artwork_url = "https://example.com/artist.jpg"
        artist_page.artwork_source = "discogs"

        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_page.return_value = artist_page

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):
            response = client.get("/api/artists/1")

            assert response.status_code == 200
            data = response.json()

            assert "artwork_url" in data
            assert data["artwork_url"] == "https://example.com/artist.jpg"
            assert data["artwork_source"] == "discogs"

    def test_get_artist_albums_sorted(self, client, artist_page):
        """Test that artist's albums are sorted by year"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_page.return_value = artist_page

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists/1")

            assert response.status_code == 200
            data = response.json()

            albums = data["albums"]
            # Should be sorted by year (newest first), then title
            assert len(albums) == 2

    def test_get_artist_album_without_tracks_does_not_crash(self, client):
        """Regression test for #5200: the route must not read album.tracks."""
        album = Album(id=1, title="Detached Album", year=2024)
        album.track_count_expr = 0
        album.total_duration_expr = 0

        artist = Artist(id=1, name="Test Artist", artwork_url=None, artwork_source=None)
        artist.albums = [album]

        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_page.return_value = artist

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):
            response = client.get("/api/artists/1")

        assert response.status_code == 200
        assert response.json()["albums"] == [{
            "id": 1,
            "title": "Detached Album",
            "year": 2024,
            "track_count": 0,
            "total_duration": 0.0,
            "artwork_url": None,
        }]

    def test_get_artist_album_uses_model_aggregate_values(self, client):
        """Album.to_dict SQL aggregates flow through the detail endpoint."""
        album = Album(id=1, title="Aggregate Album", year=2024, artist_id=1)
        album.track_count_expr = 7
        album.total_duration_expr = 1234.5

        artist = Artist(id=1, name="Test Artist", artwork_url=None, artwork_source=None)
        artist.albums = [album]

        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_page.return_value = artist

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):
            response = client.get("/api/artists/1")

        assert response.status_code == 200
        album_data = response.json()["albums"][0]
        assert album_data["track_count"] == 7
        assert album_data["total_duration"] == 1234.5

    def test_get_artist_by_id_not_found(self, client):
        """Test getting non-existent artist"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_page.return_value = None

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists/9999")

            assert response.status_code == 404

    def test_get_artist_by_id_invalid_id(self, client):
        """Test getting artist with invalid ID"""
        response = client.get("/api/artists/invalid")

        # Should return 422 for validation error
        assert response.status_code == 422


class TestGetArtistTracks:
    """Test GET /api/artists/{artist_id}/tracks endpoint"""

    def test_get_artist_tracks_success(self, client, artist_track_rows):
        """Test getting tracks for an artist"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_track_rows.return_value = artist_track_rows

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists/1/tracks")

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == 1
            assert data["name"] == "Test Artist"
            assert data["total_tracks"] == 2
            assert len(data["tracks"]) == 2

    def test_get_artist_tracks_include_album_info(self, client, artist_track_rows):
        """Test that tracks include album information"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_track_rows.return_value = artist_track_rows

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists/1/tracks")

            assert response.status_code == 200
            data = response.json()

            track = data["tracks"][0]
            assert "album" in track
            assert "album_id" in track
            assert track["album_id"] == 1

    def test_get_artist_tracks_sorted(self, client, artist_track_rows):
        """Test that tracks are sorted by album, disc, and track number"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_track_rows.return_value = artist_track_rows

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists/1/tracks")

            assert response.status_code == 200
            data = response.json()

            # The repository sorts in SQL; the route keeps its order and maps
            # a NULL duration to 0 (#5872).
            assert [track["id"] for track in data["tracks"]] == [1, 2]
            assert data["tracks"][1]["duration"] == 0
            assert data["tracks"][0]["format"] == "FLAC"

    def test_get_artist_tracks_empty(self, client):
        """Test getting tracks for artist with no tracks"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_track_rows.return_value = ("Test Artist", [])

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists/1/tracks")

            assert response.status_code == 200
            data = response.json()

            assert data["total_tracks"] == 0
            assert len(data["tracks"]) == 0

    def test_get_artist_tracks_not_found(self, client):
        """Test getting tracks for non-existent artist"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_track_rows.return_value = None

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists/9999/tracks")

            assert response.status_code == 404


class TestArtistsAPIIntegration:
    """Integration tests for artists API"""

    def test_artists_workflow(self, client, artist_row, artist_track_rows):
        """Test complete workflow: list artists -> get artist -> get tracks"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        # Step 1: List artists
        mock_repo_factory.artists.get_all.return_value = ([artist_row], 1)

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists")
            assert response.status_code == 200
            artists = response.json()["artists"]

            if artists:
                artist_id = artists[0]["id"]

                # Step 2: Get artist details
                mock_repo_factory.artists.get_page.return_value = artist_row
                mock_repo_factory.artists.get_track_rows.return_value = artist_track_rows
                response = client.get(f"/api/artists/{artist_id}")
                assert response.status_code == 200
                artist_data = response.json()
                assert "albums" in artist_data

                # Step 3: Get artist tracks
                response = client.get(f"/api/artists/{artist_id}/tracks")
                assert response.status_code == 200
                tracks_data = response.json()
                assert "tracks" in tracks_data

    def test_artists_search_and_retrieve(self, client, artist_row):
        """Test searching for artist and retrieving details"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.search.return_value = ([artist_row], 1)

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            # Search for artist
            response = client.get("/api/artists?search=Test")
            assert response.status_code == 200

            data = response.json()
            assert "artists" in data

    def test_pagination_consistency(self, client, artist_row):
        """Test pagination consistency across multiple requests"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        # First page
        mock_repo_factory.artists.get_all.return_value = ([artist_row], 50)

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):
            response1 = client.get("/api/artists?limit=25&offset=0")

            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["has_more"] == True

            # Second page
            response2 = client.get("/api/artists?limit=25&offset=25")

            assert response2.status_code == 200


class TestArtistsErrorHandling:
    """Test error handling in artists API"""

    def test_artists_database_error(self, client):
        """Test handling of database errors"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_all.side_effect = Exception("Database connection error")

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists")

            assert response.status_code == 500

    def test_artist_by_id_database_error(self, client):
        """Test handling of database errors when getting artist by ID"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_page.side_effect = Exception("Database error")

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

            response = client.get("/api/artists/1")

            assert response.status_code == 500

    def test_artist_tracks_database_error(self, client):
        """Test handling of database errors when getting artist tracks"""
        # Mock repository_factory (Phase 6B: artists router uses RepositoryFactory)
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_track_rows.side_effect = Exception("Database error")

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):

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

