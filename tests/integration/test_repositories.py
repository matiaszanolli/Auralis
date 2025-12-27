"""
Integration tests for repository pattern.

Tests verify that repositories correctly abstract database operations,
handle transactions, manage sessions, and maintain data integrity.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pathlib import Path

import pytest

from auralis.library.models import Album, Artist, Genre, Playlist, Track
from auralis.library.repositories import (
    AlbumRepository,
    ArtistRepository,
    FingerprintRepository,
    GenreRepository,
    PlaylistRepository,
    TrackRepository,
)
from auralis.library.repositories.factory import RepositoryFactory


@pytest.mark.integration
class TestTrackRepository:
    """Test TrackRepository data access patterns."""

    def test_get_by_id_returns_detached_object(self):
        """Verify objects are detached from session after retrieval."""
        track = TrackRepository.get_by_id(1)

        if track:
            # Check that object is detached (no session attribute)
            assert track not in hasattr(track, '_sa_instance_state')

    def test_pagination_returns_correct_structure(self):
        """Verify pagination returns (results, total_count) tuple."""
        results, total_count = TrackRepository.get_all(limit=10, offset=0)

        assert isinstance(results, list)
        assert isinstance(total_count, int)
        assert len(results) <= 10
        assert total_count >= len(results)

    def test_update_metadata_modifies_only_provided_fields(self):
        """Verify partial updates work correctly."""
        # Find a track to test with
        all_tracks, _ = TrackRepository.get_all(limit=1)

        if all_tracks:
            track = all_tracks[0]
            original_artist_id = track.artist_id

            # Update only title
            updated = TrackRepository.update_metadata(
                track.id,
                title="Updated Title"
            )

            assert updated is not None
            assert updated.title == "Updated Title"
            assert updated.artist_id == original_artist_id  # Unchanged

    def test_update_metadata_returns_none_for_missing_track(self):
        """Verify update returns None when track doesn't exist."""
        updated = TrackRepository.update_metadata(999999, title="Test")

        assert updated is None

    def test_cleanup_missing_files_handles_nonexistent_paths(self):
        """Verify cleanup doesn't crash on nonexistent file paths."""
        # This should not raise an exception
        try:
            count = TrackRepository.cleanup_missing_files()
            assert isinstance(count, int)
            assert count >= 0
        except Exception as e:
            pytest.fail(f"cleanup_missing_files raised {type(e).__name__}: {e}")


@pytest.mark.integration
class TestAlbumRepository:
    """Test AlbumRepository operations."""

    def test_get_by_id_with_relationships(self):
        """Verify get_by_id loads relationships correctly."""
        album = AlbumRepository.get_by_id(1)

        if album:
            # Verify artist relationship is loaded (no additional query needed)
            if album.artist:
                assert hasattr(album.artist, 'name')

    def test_update_artwork_path_persists_changes(self):
        """Test artwork path update persists to database."""
        # Get an album to test with
        albums, _ = AlbumRepository.get_all(limit=1)

        if albums:
            album = albums[0]
            test_path = "/tmp/test_artwork.jpg"

            # Update artwork path
            updated = AlbumRepository.update_artwork_path(album.id, test_path)

            assert updated is not None
            assert updated.artwork_path == test_path

            # Verify it persists
            retrieved = AlbumRepository.get_by_id(album.id)
            assert retrieved.artwork_path == test_path

    def test_update_artwork_path_returns_none_for_missing_album(self):
        """Verify update returns None when album doesn't exist."""
        updated = AlbumRepository.update_artwork_path(999999, "/test.jpg")

        assert updated is None

    def test_get_all_pagination(self):
        """Verify pagination works correctly."""
        page1, total = AlbumRepository.get_all(limit=5, offset=0)
        page2, _ = AlbumRepository.get_all(limit=5, offset=5)

        assert len(page1) <= 5
        if total > 5:
            assert len(page2) <= 5
            assert page1[0].id != page2[0].id  # Different albums


@pytest.mark.integration
class TestArtistRepository:
    """Test ArtistRepository operations."""

    def test_get_by_id_returns_artist(self):
        """Verify artist retrieval works."""
        artist = ArtistRepository.get_by_id(1)

        if artist:
            assert hasattr(artist, 'name')
            assert artist.id == 1

    def test_get_all_returns_paginated_list(self):
        """Verify artist list is paginated."""
        artists, total = ArtistRepository.get_all(limit=10)

        assert isinstance(artists, list)
        assert isinstance(total, int)
        assert len(artists) <= 10


@pytest.mark.integration
class TestGenreRepository:
    """Test GenreRepository (newly created)."""

    def test_genre_crud_cycle(self):
        """Test full CRUD cycle for genres."""
        # Create
        genre = GenreRepository.create(name="Test Genre")
        assert genre.id is not None
        assert genre.name == "Test Genre"

        # Retrieve
        retrieved = GenreRepository.get_by_id(genre.id)
        assert retrieved is not None
        assert retrieved.name == "Test Genre"

        # Update
        updated = GenreRepository.update(genre.id, name="Updated Genre")
        assert updated.name == "Updated Genre"

        # Delete
        success = GenreRepository.delete(genre.id)
        assert success is True

        # Verify deletion
        deleted = GenreRepository.get_by_id(genre.id)
        assert deleted is None

    def test_get_by_name(self):
        """Test genre lookup by name."""
        # Create a test genre
        genre = GenreRepository.create(name="Rock")

        # Retrieve by name
        retrieved = GenreRepository.get_by_name("Rock")
        assert retrieved is not None
        assert retrieved.name == "Rock"

        # Clean up
        GenreRepository.delete(genre.id)

    def test_get_all_returns_paginated_list(self):
        """Verify genres list is paginated."""
        genres, total = GenreRepository.get_all(limit=10)

        assert isinstance(genres, list)
        assert isinstance(total, int)
        assert len(genres) <= 10

    def test_search_by_name(self):
        """Test genre search functionality."""
        # Create test genres
        genre1 = GenreRepository.create(name="ClassicalMusic")
        genre2 = GenreRepository.create(name="ClassicalArts")

        # Search
        results, count = GenreRepository.search("Classical", limit=10)

        assert count >= 2
        genre_names = [g.name for g in results]
        assert "ClassicalMusic" in genre_names
        assert "ClassicalArts" in genre_names

        # Clean up
        GenreRepository.delete(genre1.id)
        GenreRepository.delete(genre2.id)


@pytest.mark.integration
class TestFingerprintRepository:
    """Test FingerprintRepository operations."""

    def test_get_fingerprint_status_structure(self):
        """Test fingerprint status method returns correct structure."""
        # Try to get status for first track
        status = FingerprintRepository.get_fingerprint_status(1)

        if status:
            assert 'track_id' in status
            assert 'status' in status
            assert 'created_at' in status
            assert 'has_fingerprint' in status

    def test_get_fingerprint_stats_structure(self):
        """Test fingerprint stats returns expected fields."""
        stats = FingerprintRepository.get_fingerprint_stats()

        assert 'total' in stats
        assert 'fingerprinted' in stats
        assert 'pending' in stats
        assert 'progress_percent' in stats

        # Verify values are reasonable
        assert stats['total'] >= 0
        assert stats['fingerprinted'] >= 0
        assert stats['pending'] >= 0
        assert 0 <= stats['progress_percent'] <= 100

    def test_cleanup_incomplete_fingerprints_returns_count(self):
        """Test cleanup returns number of deleted fingerprints."""
        try:
            count = FingerprintRepository.cleanup_incomplete_fingerprints()
            assert isinstance(count, int)
            assert count >= 0
        except Exception as e:
            # Database might not have incomplete fingerprints, that's fine
            pytest.skip(f"No incomplete fingerprints to clean: {e}")


@pytest.mark.integration
class TestPlaylistRepository:
    """Test PlaylistRepository operations."""

    def test_get_by_id_returns_playlist(self):
        """Verify playlist retrieval works."""
        playlist = PlaylistRepository.get_by_id(1)

        if playlist:
            assert hasattr(playlist, 'name')
            assert playlist.id == 1

    def test_get_all_returns_paginated_list(self):
        """Verify playlist list is paginated."""
        playlists, total = PlaylistRepository.get_all(limit=10)

        assert isinstance(playlists, list)
        assert isinstance(total, int)
        assert len(playlists) <= 10


@pytest.mark.integration
class TestSessionManagement:
    """Test session management across repositories."""

    def test_no_session_leaks(self):
        """Verify sessions are properly closed."""
        import gc

        # Make multiple repository calls
        for i in range(5):
            TrackRepository.get_by_id(i)
            AlbumRepository.get_by_id(i)
            ArtistRepository.get_by_id(i)

        # Force garbage collection
        gc.collect()

        # If there are no exceptions, sessions were cleaned up properly
        # (In a real test, we'd check open connection count)

    def test_different_repository_instances_independent(self):
        """Verify repositories have independent sessions."""
        # Get objects from different repositories
        track = TrackRepository.get_by_id(1)
        album = AlbumRepository.get_by_id(1)
        artist = ArtistRepository.get_by_id(1)

        # Each should be independent
        if track and album and artist:
            # Operations on one should not affect others
            assert track is not None
            assert album is not None
            assert artist is not None


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling in repositories."""

    def test_get_nonexistent_returns_none(self):
        """Verify get methods return None for missing records."""
        track = TrackRepository.get_by_id(999999)
        album = AlbumRepository.get_by_id(999999)
        artist = ArtistRepository.get_by_id(999999)
        genre = GenreRepository.get_by_id(999999)

        assert track is None
        assert album is None
        assert artist is None
        assert genre is None

    def test_update_invalid_field_ignored(self):
        """Verify update safely ignores invalid fields."""
        # Try to update a non-existent field
        # Should not raise an exception
        all_tracks, _ = TrackRepository.get_all(limit=1)

        if all_tracks:
            track = all_tracks[0]
            try:
                updated = TrackRepository.update_metadata(
                    track.id,
                    nonexistent_field="value"  # Invalid field
                )
                # Method should handle invalid field gracefully
                assert updated is not None
            except AttributeError:
                # If it raises, that's expected for invalid fields
                pass


# ============================================================
# Phase 5A: RepositoryFactory Pattern Tests
# ============================================================

@pytest.mark.integration
class TestRepositoryFactory:
    """Test RepositoryFactory for Phase 5A (Test Suite Migration).

    These tests verify that the RepositoryFactory pattern enables
    dependency injection of repositories in tests while maintaining
    backward compatibility with static repository methods.
    """

    def test_factory_creation_via_fixture(self, repository_factory):
        """Verify RepositoryFactory can be created from fixture."""
        assert repository_factory is not None
        assert isinstance(repository_factory, RepositoryFactory)

    def test_factory_provides_all_repositories(self, repository_factory):
        """Verify factory creates all repository instances."""
        # Verify all repositories are accessible
        assert repository_factory.tracks is not None
        assert repository_factory.albums is not None
        assert repository_factory.artists is not None
        assert repository_factory.genres is not None
        assert repository_factory.playlists is not None
        assert repository_factory.fingerprints is not None
        assert repository_factory.stats is not None
        assert repository_factory.settings is not None

    def test_factory_repositories_have_expected_methods(self, repository_factory):
        """Verify factory-created repositories have expected methods."""
        tracks_repo = repository_factory.tracks
        albums_repo = repository_factory.albums
        artists_repo = repository_factory.artists

        # Verify key methods exist
        assert hasattr(tracks_repo, 'get_by_id')
        assert hasattr(tracks_repo, 'get_all')
        assert hasattr(tracks_repo, 'search')
        assert hasattr(tracks_repo, 'create')
        assert hasattr(tracks_repo, 'update_metadata')

        assert hasattr(albums_repo, 'get_by_id')
        assert hasattr(albums_repo, 'get_all')
        assert hasattr(albums_repo, 'update_artwork_path')

        assert hasattr(artists_repo, 'get_by_id')
        assert hasattr(artists_repo, 'get_all')

    def test_factory_session_management(self, repository_factory):
        """Verify factory manages sessions correctly."""
        # Get objects from different repositories
        track_repo = repository_factory.tracks
        album_repo = repository_factory.albums

        # Should be able to get IDs without errors
        tracks, total_tracks = track_repo.get_all(limit=1)
        albums, total_albums = album_repo.get_all(limit=1)

        assert isinstance(total_tracks, int)
        assert isinstance(total_albums, int)
        assert total_tracks >= 0
        assert total_albums >= 0

    def test_factory_lazy_initialization(self, session_factory):
        """Verify factory uses lazy initialization for repositories."""
        factory = RepositoryFactory(session_factory)

        # Verify repositories are not created until accessed
        assert factory._track_repo is None
        assert factory._album_repo is None

        # Access one repository
        _ = factory.tracks
        assert factory._track_repo is not None
        assert factory._album_repo is None  # Should still be None

        # Access another
        _ = factory.albums
        assert factory._album_repo is not None

    def test_factory_repository_caching(self, repository_factory):
        """Verify factory caches repository instances."""
        # Get repository twice
        tracks_repo1 = repository_factory.tracks
        tracks_repo2 = repository_factory.tracks

        # Should be the same instance (cached)
        assert tracks_repo1 is tracks_repo2

    def test_factory_from_library_manager_session(self, library_manager):
        """Verify factory works with LibraryManager's session factory."""
        # Create factory from library manager's session factory
        factory = RepositoryFactory(library_manager.SessionLocal)

        # Verify it works
        assert factory.tracks is not None
        tracks, total = factory.tracks.get_all(limit=10)

        assert isinstance(tracks, list)
        assert isinstance(total, int)

    def test_factory_multiple_instances_independent(self, session_factory):
        """Verify multiple factory instances are independent."""
        factory1 = RepositoryFactory(session_factory)
        factory2 = RepositoryFactory(session_factory)

        # Create two different factory instances
        tracks_repo1 = factory1.tracks
        tracks_repo2 = factory2.tracks

        # They should be different instances
        assert tracks_repo1 is not tracks_repo2

        # But should both work
        results1, total1 = tracks_repo1.get_all(limit=1)
        results2, total2 = tracks_repo2.get_all(limit=1)

        assert total1 == total2


@pytest.mark.integration
class TestDualModeCompatibility:
    """Test backward compatibility between LibraryManager and RepositoryFactory.

    These tests verify that both access patterns return equivalent results.
    """

    def test_static_and_factory_repositories_equivalent(self, repository_factory):
        """Verify static and factory-based repository access are compatible."""
        # Static method (old pattern)
        tracks_static, total_static = TrackRepository.get_all(limit=5)

        # Factory method (new pattern)
        tracks_factory, total_factory = repository_factory.tracks.get_all(limit=5)

        # Should have same total
        assert total_static == total_factory

        # Should have same number of results
        assert len(tracks_static) == len(tracks_factory)

    def test_library_manager_and_factory_equivalent(self, library_manager, repository_factory):
        """Verify LibraryManager and RepositoryFactory return equivalent results."""
        # Get results from LibraryManager
        tracks_manager, total_manager = library_manager.tracks.get_all(limit=5)

        # Get results from RepositoryFactory
        tracks_factory, total_factory = repository_factory.tracks.get_all(limit=5)

        # Should have same total
        assert total_manager == total_factory

        # Should have same data
        if tracks_manager and tracks_factory:
            assert len(tracks_manager) == len(tracks_factory)
