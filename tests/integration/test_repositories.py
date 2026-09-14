"""
Integration tests for repository pattern.

Tests verify that repositories correctly abstract database operations,
handle transactions, manage sessions, and maintain data integrity.

#5192: every repository method used to be called on the CLASS
(``TrackRepository.get_by_id(1)``) rather than on an instance obtained from
``RepositoryFactory``/``session_factory`` — every repository method takes
``self`` (and most need a bound ``session_factory``), so the literal first
argument bound to ``self`` instead of the intended parameter, and every one
of these 29 tests raised ``TypeError`` rather than exercising any real
behavior. It also implicitly ran against the developer's real
``~/.auralis/library.db`` (unseeded "if track:" existence checks) rather
than an isolated test database.

Rewritten against the current idiom: the ``repository_factory`` fixture
(session-backed by a fresh temp SQLite DB per test, see tests/conftest.py)
that ``TestRepositoryFactory``/``TestDualModeCompatibility`` below already
used correctly, matching the pattern established in
tests/integration/test_library_scan_persist_query.py. Every test now seeds
its own data (each test gets an empty database) and asserts real values,
not just "did not raise".

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from sqlalchemy.orm import object_session

import pytest

from auralis.library.repositories.factory import RepositoryFactory

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_track(tracks_repo, *, filepath, title, artists=None, album=None,
                genres=None, duration=180.0, sample_rate=44100, channels=2,
                format='FLAC', **extra):
    """Add a synthetic track directly via TrackRepository.add() — no file
    needs to exist on disk since format/sample_rate/channels are supplied
    explicitly. Matches test_library_scan_persist_query.py's helper."""
    track_info = {
        'filepath': filepath,
        'title': title,
        'artists': artists or [],
        'duration': duration,
        'sample_rate': sample_rate,
        'channels': channels,
        'format': format,
        **extra,
    }
    if album:
        track_info['album'] = album
    if genres:
        track_info['genres'] = genres
    track = tracks_repo.add(track_info)
    assert track is not None, f"failed to add track {title!r}"
    return track


# All 25 TrackFingerprint dimensions — matches
# tests/auralis/library/test_fingerprint_repository_blob_preservation.py's
# _SAMPLE_FP, the established fixture shape for seeding a fingerprint row.
_SAMPLE_FP: dict = {
    'sub_bass_pct': 0.1, 'bass_pct': 0.2, 'low_mid_pct': 0.15,
    'mid_pct': 0.25, 'upper_mid_pct': 0.1, 'presence_pct': 0.1, 'air_pct': 0.1,
    'lufs': -14.0, 'crest_db': 6.0, 'bass_mid_ratio': 0.8,
    'tempo_bpm': 120.0, 'rhythm_stability': 0.9, 'transient_density': 0.5,
    'silence_ratio': 0.05, 'spectral_centroid': 3000.0, 'spectral_rolloff': 8000.0,
    'spectral_flatness': 0.3, 'harmonic_ratio': 0.7, 'pitch_stability': 0.85,
    'chroma_energy': 0.6, 'dynamic_range_variation': 3.0,
    'loudness_variation_std': 1.5, 'peak_consistency': 0.9,
    'stereo_width': 0.5, 'phase_correlation': 0.95,
}


class TestTrackRepository:
    """Test TrackRepository data access patterns."""

    def test_get_by_id_returns_detached_object(self, repository_factory):
        """Repositories expunge() everything they return (CLAUDE.md's
        "Detached ORM instances" invariant) — the object must not still be
        attached to a live session."""
        tracks = repository_factory.tracks
        added = _add_track(tracks, filepath="/music/a.flac", title="A")

        track = tracks.get_by_id(added.id)

        assert track is not None
        assert track.id == added.id
        assert object_session(track) is None, "returned track is still session-attached"

    def test_pagination_returns_correct_structure(self, repository_factory):
        """Verify pagination returns (results, total_count) tuple."""
        tracks = repository_factory.tracks
        for i in range(15):
            _add_track(tracks, filepath=f"/music/page_{i}.flac", title=f"Track {i}")

        results, total_count = tracks.get_all(limit=10, offset=0)

        assert isinstance(results, list)
        assert isinstance(total_count, int)
        assert len(results) == 10
        assert total_count == 15

    def test_update_metadata_modifies_only_provided_fields(self, repository_factory):
        """Verify partial updates work correctly."""
        tracks = repository_factory.tracks
        added = _add_track(
            tracks, filepath="/music/b.flac", title="Original Title",
            artists=["Original Artist"],
        )

        updated = tracks.update_metadata(added.id, title="Updated Title")

        assert updated is not None
        assert updated.title == "Updated Title"
        # #5192: the original test read a nonexistent `track.artist_id`
        # (Track.artists is a many-to-many relationship, no singular FK) —
        # assert the actual relationship survived the partial update instead.
        assert [a.name for a in updated.artists] == ["Original Artist"]

    def test_update_metadata_returns_none_for_missing_track(self, repository_factory):
        """Verify update returns None when track doesn't exist."""
        updated = repository_factory.tracks.update_metadata(999999, title="Test")

        assert updated is None

    def test_cleanup_missing_files_handles_nonexistent_paths(self, repository_factory, tmp_path):
        """A track whose file no longer exists (but whose parent directory
        does — #2525's unmounted-volume guard only skips when the parent is
        gone too) is removed by cleanup."""
        tracks = repository_factory.tracks
        missing_path = str(tmp_path / "deleted.flac")
        added = _add_track(tracks, filepath=missing_path, title="Gone")

        removed_count = tracks.cleanup_missing_files()

        assert removed_count == 1
        assert tracks.get_by_id(added.id) is None


class TestAlbumRepository:
    """Test AlbumRepository operations."""

    def test_get_by_id_with_relationships(self, repository_factory):
        """Verify get_by_id loads the artist relationship without a
        DetachedInstanceError (CLAUDE.md's eager-load invariant)."""
        tracks = repository_factory.tracks
        _add_track(
            tracks, filepath="/music/c.flac", title="C",
            artists=["Some Artist"], album="Some Album",
        )
        albums, _ = repository_factory.albums.get_all(limit=1)
        assert albums, "track add() should have created an album"

        album = repository_factory.albums.get_by_id(albums[0].id)

        assert album is not None
        assert album.artist is not None
        assert album.artist.name == "Some Artist"

    def test_update_artwork_path_persists_changes(self, repository_factory):
        """Test artwork path update persists to database."""
        tracks = repository_factory.tracks
        _add_track(tracks, filepath="/music/d.flac", title="D", artists=["Artist D"], album="Album D")
        albums_repo = repository_factory.albums
        albums, _ = albums_repo.get_all(limit=1)
        album = albums[0]
        test_path = "/tmp/test_artwork.jpg"

        updated = albums_repo.update_artwork_path(album.id, test_path)

        assert updated is not None
        assert updated.artwork_path == test_path
        # Verify it persists — a fresh read, not the same in-memory object.
        retrieved = albums_repo.get_by_id(album.id)
        assert retrieved.artwork_path == test_path

    def test_update_artwork_path_returns_none_for_missing_album(self, repository_factory):
        """Verify update returns None when album doesn't exist."""
        updated = repository_factory.albums.update_artwork_path(999999, "/test.jpg")

        assert updated is None

    def test_get_all_pagination(self, repository_factory):
        """Verify pagination works correctly across distinct albums."""
        tracks = repository_factory.tracks
        for i in range(7):
            _add_track(
                tracks, filepath=f"/music/album_{i}/track.flac",
                title=f"Track {i}", artists=[f"Artist {i}"], album=f"Album {i}",
            )
        albums_repo = repository_factory.albums

        page1, total = albums_repo.get_all(limit=5, offset=0)
        page2, _ = albums_repo.get_all(limit=5, offset=5)

        assert total == 7
        assert len(page1) == 5
        assert len(page2) == 2
        assert {a.id for a in page1}.isdisjoint({a.id for a in page2})


class TestArtistRepository:
    """Test ArtistRepository operations."""

    def test_get_by_id_returns_artist(self, repository_factory):
        """Verify artist retrieval works."""
        tracks = repository_factory.tracks
        _add_track(tracks, filepath="/music/e.flac", title="E", artists=["Real Artist"])
        artists_repo = repository_factory.artists
        artists, _ = artists_repo.get_all(limit=1)
        seeded = artists[0]

        artist = artists_repo.get_by_id(seeded.id)

        assert artist is not None
        assert artist.id == seeded.id
        assert artist.name == "Real Artist"

    def test_get_all_returns_paginated_list(self, repository_factory):
        """Verify artist list is paginated."""
        tracks = repository_factory.tracks
        for i in range(12):
            _add_track(tracks, filepath=f"/music/artist_{i}.flac", title=f"T{i}", artists=[f"Artist {i}"])

        artists, total = repository_factory.artists.get_all(limit=10)

        assert isinstance(artists, list)
        assert total == 12
        assert len(artists) == 10


class TestGenreRepository:
    """Test GenreRepository."""

    def test_genre_crud_cycle(self, repository_factory):
        """Test full CRUD cycle for genres."""
        genres_repo = repository_factory.genres

        genre = genres_repo.create(name="Test Genre")
        assert genre.id is not None
        assert genre.name == "Test Genre"

        retrieved = genres_repo.get_by_id(genre.id)
        assert retrieved is not None
        assert retrieved.name == "Test Genre"

        updated = genres_repo.update(genre.id, name="Updated Genre")
        assert updated.name == "Updated Genre"

        success = genres_repo.delete(genre.id)
        assert success is True

        deleted = genres_repo.get_by_id(genre.id)
        assert deleted is None

    def test_get_by_name(self, repository_factory):
        """Test genre lookup by name."""
        genres_repo = repository_factory.genres
        genres_repo.create(name="Rock")

        retrieved = genres_repo.get_by_name("Rock")

        assert retrieved is not None
        assert retrieved.name == "Rock"

    def test_get_all_returns_paginated_list(self, repository_factory):
        """Verify genres list is paginated."""
        genres_repo = repository_factory.genres
        for i in range(12):
            genres_repo.create(name=f"Genre {i}")

        genres, total = genres_repo.get_all(limit=10)

        assert isinstance(genres, list)
        assert total == 12
        assert len(genres) == 10

    def test_search_by_name(self, repository_factory):
        """Test genre search functionality."""
        genres_repo = repository_factory.genres
        genres_repo.create(name="ClassicalMusic")
        genres_repo.create(name="ClassicalArts")
        genres_repo.create(name="Jazz")

        results, count = genres_repo.search("Classical", limit=10)

        assert count == 2
        genre_names = {g.name for g in results}
        assert genre_names == {"ClassicalMusic", "ClassicalArts"}


class TestFingerprintRepository:
    """Test FingerprintRepository operations."""

    def test_get_fingerprint_status_structure(self, repository_factory):
        """A seeded fingerprint row round-trips through get_fingerprint_status."""
        tracks = repository_factory.tracks
        added = _add_track(tracks, filepath="/music/f.flac", title="F")
        fp_repo = repository_factory.fingerprints
        fp_repo.add(track_id=added.id, fingerprint_data=_SAMPLE_FP)

        status = fp_repo.get_fingerprint_status(added.id)

        assert status is not None
        assert status['track_id'] == added.id
        assert status['has_fingerprint'] is True
        assert status['created_at'] is not None

    def test_get_fingerprint_status_none_for_track_without_fingerprint(self, repository_factory):
        tracks = repository_factory.tracks
        added = _add_track(tracks, filepath="/music/g.flac", title="G")

        status = repository_factory.fingerprints.get_fingerprint_status(added.id)

        assert status is None

    def test_get_fingerprint_stats_structure(self, repository_factory):
        """Test fingerprint stats returns expected fields with real counts."""
        tracks = repository_factory.tracks
        for i in range(3):
            _add_track(tracks, filepath=f"/music/stat_{i}.flac", title=f"S{i}")

        stats = repository_factory.fingerprints.get_fingerprint_stats()

        assert 'total' in stats
        assert 'fingerprinted' in stats
        assert 'pending' in stats
        assert 'progress_percent' in stats
        assert stats['total'] == 3
        assert stats['fingerprinted'] == 0
        assert stats['pending'] == 3
        assert stats['progress_percent'] == 0

    def test_cleanup_incomplete_fingerprints_returns_count(self, repository_factory):
        """Test cleanup returns number of deleted fingerprints (0 on a
        freshly seeded, fully-consistent database — no incomplete rows)."""
        count = repository_factory.fingerprints.cleanup_incomplete_fingerprints()

        assert isinstance(count, int)
        assert count == 0


class TestPlaylistRepository:
    """Test PlaylistRepository operations."""

    def test_get_by_id_returns_playlist(self, repository_factory):
        """Verify playlist retrieval works."""
        playlists_repo = repository_factory.playlists
        created = playlists_repo.create(name="My Playlist")

        playlist = playlists_repo.get_by_id(created.id)

        assert playlist is not None
        assert playlist.id == created.id
        assert playlist.name == "My Playlist"

    def test_get_all_returns_paginated_list(self, repository_factory):
        """Verify playlist list is paginated."""
        playlists_repo = repository_factory.playlists
        for i in range(12):
            playlists_repo.create(name=f"Playlist {i}")

        playlists, total = playlists_repo.get_all(limit=10)

        assert isinstance(playlists, list)
        assert total == 12
        assert len(playlists) == 10


class TestSessionManagement:
    """Test session management across repositories."""

    def test_no_session_leaks(self, repository_factory):
        """Repeated repository calls across multiple repos must not raise
        or leave attached instances — expunge() runs on every return."""
        tracks = repository_factory.tracks
        added = [
            _add_track(tracks, filepath=f"/music/leak_{i}.flac", title=f"L{i}", artists=[f"Art{i}"], album=f"Alb{i}")
            for i in range(5)
        ]
        albums, _ = repository_factory.albums.get_all(limit=5)
        artists, _ = repository_factory.artists.get_all(limit=5)
        assert len(albums) == 5 and len(artists) == 5, "loop bodies below must not run vacuously"

        for t in added:
            track = tracks.get_by_id(t.id)
            assert object_session(track) is None
        for a in albums:
            album = repository_factory.albums.get_by_id(a.id)
            assert object_session(album) is None
        for ar in artists:
            artist = repository_factory.artists.get_by_id(ar.id)
            assert object_session(artist) is None

    def test_different_repository_instances_independent(self, repository_factory):
        """Repositories obtained from the same factory are independent
        objects, each backed by its own model — not the same instance
        wearing different names."""
        tracks = repository_factory.tracks
        added = _add_track(tracks, filepath="/music/h.flac", title="H", artists=["Artist H"], album="Alb H")
        albums, _ = repository_factory.albums.get_all(limit=1)

        track = tracks.get_by_id(added.id)
        album = repository_factory.albums.get_by_id(albums[0].id)

        assert repository_factory.tracks is not repository_factory.albums
        assert track.__class__.__name__ == "Track"
        assert album.__class__.__name__ == "Album"
        assert track.id != album.id or type(track) is not type(album)


class TestErrorHandling:
    """Test error handling in repositories."""

    def test_get_nonexistent_returns_none(self, repository_factory):
        """Verify get methods return None for missing records."""
        assert repository_factory.tracks.get_by_id(999999) is None
        assert repository_factory.albums.get_by_id(999999) is None
        assert repository_factory.artists.get_by_id(999999) is None
        assert repository_factory.genres.get_by_id(999999) is None

    def test_update_invalid_field_ignored(self, repository_factory):
        """An unknown field passed to update_metadata is silently dropped
        (#4555's metadata-writable-columns allowlist) — the track comes back
        unchanged rather than raising."""
        tracks = repository_factory.tracks
        added = _add_track(tracks, filepath="/music/i.flac", title="Original")

        updated = tracks.update_metadata(added.id, nonexistent_field="value")

        assert updated is not None
        assert updated.title == "Original"
        assert not hasattr(updated, "nonexistent_field")


# ============================================================
# Phase 5A: RepositoryFactory Pattern Tests
# ============================================================

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
        """Verify factory creates all repository instances of the right type."""
        assert type(repository_factory.tracks).__name__ == "TrackRepository"
        assert type(repository_factory.albums).__name__ == "AlbumRepository"
        assert type(repository_factory.artists).__name__ == "ArtistRepository"
        assert type(repository_factory.genres).__name__ == "GenreRepository"
        assert type(repository_factory.playlists).__name__ == "PlaylistRepository"
        assert type(repository_factory.fingerprints).__name__ == "FingerprintRepository"
        assert type(repository_factory.stats).__name__ == "StatsRepository"
        assert type(repository_factory.settings).__name__ == "SettingsRepository"

    def test_factory_repositories_have_expected_methods(self, repository_factory):
        """Verify factory-created repositories have expected methods.

        #5192: the original assertion checked for `tracks_repo.create`,
        which has never existed — TrackRepository's write method is `add()`
        (see track_repository_lifecycle.py).
        """
        tracks_repo = repository_factory.tracks
        albums_repo = repository_factory.albums
        artists_repo = repository_factory.artists

        assert hasattr(tracks_repo, 'get_by_id')
        assert hasattr(tracks_repo, 'get_all')
        assert hasattr(tracks_repo, 'search')
        assert hasattr(tracks_repo, 'add')
        assert hasattr(tracks_repo, 'update_metadata')

        assert hasattr(albums_repo, 'get_by_id')
        assert hasattr(albums_repo, 'get_all')
        assert hasattr(albums_repo, 'update_artwork_path')

        assert hasattr(artists_repo, 'get_by_id')
        assert hasattr(artists_repo, 'get_all')

    def test_factory_session_management(self, repository_factory):
        """Verify factory manages sessions correctly."""
        track_repo = repository_factory.tracks
        album_repo = repository_factory.albums

        _tracks, total_tracks = track_repo.get_all(limit=1)
        _albums, total_albums = album_repo.get_all(limit=1)

        assert isinstance(total_tracks, int)
        assert isinstance(total_albums, int)
        assert total_tracks == 0
        assert total_albums == 0

    def test_factory_lazy_initialization(self, session_factory):
        """Verify factory uses lazy initialization for repositories.

        #5192: TrackRepository's own lazy-init passes `album_repository=self.albums`
        (track_repository.py's `add()` needs it to resolve album relationships),
        so accessing `.tracks` for the first time also eagerly creates
        `_album_repo` as an intentional side effect — the original assertion
        (`_album_repo is None` after only touching `.tracks`) predates that
        dependency and no longer holds. `.artists` has no such coupling and
        stays lazy.
        """
        factory = RepositoryFactory(session_factory)

        assert factory._track_repo is None
        assert factory._album_repo is None
        assert factory._artist_repo is None

        _ = factory.tracks
        assert factory._track_repo is not None
        assert factory._album_repo is not None  # eager side effect, by design
        assert factory._artist_repo is None  # still untouched

        _ = factory.artists
        assert factory._artist_repo is not None

    def test_factory_repository_caching(self, repository_factory):
        """Verify factory caches repository instances."""
        tracks_repo1 = repository_factory.tracks
        tracks_repo2 = repository_factory.tracks

        assert tracks_repo1 is tracks_repo2

    def test_factory_from_library_database_session(self, library_database):
        """Verify factory works with LibraryDatabase's session factory."""
        factory = RepositoryFactory(library_database.SessionLocal)

        assert factory.tracks is not None
        tracks, total = factory.tracks.get_all(limit=10)

        assert isinstance(tracks, list)
        assert total == 0

    def test_factory_multiple_instances_independent(self, session_factory):
        """Verify multiple factory instances are independent."""
        factory1 = RepositoryFactory(session_factory)
        factory2 = RepositoryFactory(session_factory)

        tracks_repo1 = factory1.tracks
        tracks_repo2 = factory2.tracks

        assert tracks_repo1 is not tracks_repo2

        _results1, total1 = tracks_repo1.get_all(limit=1)
        _results2, total2 = tracks_repo2.get_all(limit=1)

        assert total1 == total2


class TestDualModeCompatibility:
    """Test backward compatibility between LibraryDatabase and RepositoryFactory.

    These tests verify that both access patterns return equivalent results
    against the SAME database.
    """

    def test_library_database_and_factory_share_the_same_backing_store(self, library_database):
        """A factory built from library_database.SessionLocal reads what
        library_database.tracks itself wrote — the two are different
        objects over the same database, not two separate stores."""
        added = _add_track(library_database.tracks, filepath="/music/j.flac", title="J")
        factory = RepositoryFactory(library_database.SessionLocal)

        tracks_manager, total_manager = library_database.tracks.get_all(limit=5)
        tracks_factory, total_factory = factory.tracks.get_all(limit=5)

        assert total_manager == total_factory == 1
        assert {t.id for t in tracks_manager} == {t.id for t in tracks_factory} == {added.id}

    def test_library_database_and_factory_equivalent(self, library_database, repository_factory):
        """repository_factory and library_database are two independent
        databases (separate temp_test_db fixtures) — both must behave
        identically against their own empty state."""
        tracks_manager, total_manager = library_database.tracks.get_all(limit=5)
        tracks_factory, total_factory = repository_factory.tracks.get_all(limit=5)

        assert total_manager == total_factory == 0
        assert tracks_manager == tracks_factory == []
