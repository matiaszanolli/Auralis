"""
Regression tests for DetachedInstanceError fix (#2070)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that repository methods return ORM objects that remain
accessible after the session is closed. Accessing eagerly loaded
relationships (.artists, .album, .tracks) must not raise
DetachedInstanceError.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest

from auralis.library.models import Album, Artist, Genre, Track


class TestTrackRepositoryDetachedAccess:
    """Verify TrackRepository methods return safely detached objects"""

    def _add_test_track(self, track_repository, session_factory, **overrides):
        """Helper to add a track with relationships via repository"""
        defaults = {
            'title': 'Test Track',
            'filepath': '/tmp/test_track.wav',
            'duration': 180.0,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'artists': ['Test Artist'],
            'album': 'Test Album',
            'genres': ['Rock'],
        }
        defaults.update(overrides)
        return track_repository.add(defaults)

    def test_get_by_id_artists_accessible(self, track_repository, session_factory):
        """get_by_id() result must allow .artists access without error"""
        track = self._add_test_track(track_repository, session_factory)
        assert track is not None

        result = track_repository.get_by_id(track.id)
        assert result is not None
        # This line would raise DetachedInstanceError before the fix
        artists = result.artists
        assert len(artists) >= 1
        assert artists[0].name == 'Test Artist'

    def test_get_by_id_album_accessible(self, track_repository, session_factory):
        """get_by_id() result must allow .album access without error"""
        track = self._add_test_track(track_repository, session_factory)

        result = track_repository.get_by_id(track.id)
        assert result is not None
        album = result.album
        assert album is not None
        assert album.title == 'Test Album'

    def test_get_by_path_relationships_accessible(self, track_repository, session_factory):
        """get_by_path() result must have accessible relationships"""
        filepath = '/tmp/test_by_path.wav'
        track = self._add_test_track(
            track_repository, session_factory, filepath=filepath
        )

        result = track_repository.get_by_path(filepath)
        assert result is not None
        assert result.artists[0].name == 'Test Artist'
        assert result.album.title == 'Test Album'

    def test_search_results_accessible(self, track_repository, session_factory):
        """search() results must have accessible relationships"""
        self._add_test_track(
            track_repository, session_factory,
            title='Searchable Song',
            filepath='/tmp/searchable.wav'
        )

        results, total = track_repository.search('Searchable')
        assert total >= 1
        for track in results:
            # Must not raise DetachedInstanceError
            _ = track.title
            _ = track.artists
            _ = track.album

    def test_get_all_relationships_accessible(self, track_repository, session_factory):
        """get_all() results must have accessible relationships"""
        self._add_test_track(
            track_repository, session_factory,
            filepath='/tmp/all_test.wav'
        )

        tracks, total = track_repository.get_all(limit=10)
        assert total >= 1
        for track in tracks:
            _ = track.artists
            _ = track.album

    def test_get_recent_relationships_accessible(self, track_repository, session_factory):
        """get_recent() results must have accessible relationships"""
        self._add_test_track(
            track_repository, session_factory,
            filepath='/tmp/recent_test.wav'
        )

        tracks, total = track_repository.get_recent(limit=10)
        assert total >= 1
        for track in tracks:
            _ = track.artists
            _ = track.album

    def test_get_popular_relationships_accessible(self, track_repository, session_factory):
        """get_popular() results must have accessible relationships"""
        self._add_test_track(
            track_repository, session_factory,
            filepath='/tmp/popular_test.wav'
        )

        tracks, total = track_repository.get_popular(limit=10)
        assert total >= 1
        for track in tracks:
            _ = track.artists
            _ = track.album

    def test_get_favorites_relationships_accessible(self, track_repository, session_factory):
        """get_favorites() results must have accessible relationships"""
        track = self._add_test_track(
            track_repository, session_factory,
            filepath='/tmp/fav_test.wav'
        )
        track_repository.set_favorite(track.id, True)

        tracks, total = track_repository.get_favorites(limit=10)
        assert total >= 1
        for track in tracks:
            _ = track.artists
            _ = track.album

    def test_update_returns_accessible_object(self, track_repository, session_factory):
        """update() must return object with accessible relationships"""
        track = self._add_test_track(
            track_repository, session_factory,
            filepath='/tmp/update_test.wav'
        )

        updated = track_repository.update(track.id, {'title': 'Updated Title'})
        assert updated is not None
        assert updated.title == 'Updated Title'
        _ = updated.artists
        _ = updated.album

    def test_add_existing_track_returns_accessible_object(self, track_repository, session_factory):
        """add() with existing filepath must return accessible object"""
        filepath = '/tmp/existing_test.wav'
        self._add_test_track(
            track_repository, session_factory,
            filepath=filepath
        )

        # Adding again should return existing track
        existing = track_repository.add({
            'title': 'Duplicate',
            'filepath': filepath,
            'artists': ['Test Artist'],
        })
        assert existing is not None
        _ = existing.artists
        _ = existing.album


class TestAlbumRepositoryDetachedAccess:
    """Verify AlbumRepository methods return safely detached objects"""

    def _setup_album(self, track_repository, session_factory):
        """Create a track (and implicitly an album) for testing"""
        return track_repository.add({
            'title': 'Album Test Track',
            'filepath': '/tmp/album_test.wav',
            'duration': 200.0,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'artists': ['Album Artist'],
            'album': 'Test Album For Detached',
        })

    def test_get_by_id_relationships_accessible(
        self, album_repository, track_repository, session_factory
    ):
        """get_by_id() must return album with accessible .artist and .tracks"""
        track = self._setup_album(track_repository, session_factory)
        assert track is not None
        assert track.album is not None

        album = album_repository.get_by_id(track.album.id)
        assert album is not None
        # Must not raise DetachedInstanceError
        _ = album.artist
        _ = album.tracks
        assert len(album.tracks) >= 1

    def test_get_by_title_relationships_accessible(
        self, album_repository, track_repository, session_factory
    ):
        """get_by_title() must return album with accessible relationships
        (fixes #4236 — sibling of get_by_id's #2406 fix; per-item
        session.expunge(album) does not cascade to album.tracks)."""
        self._setup_album(track_repository, session_factory)

        album = album_repository.get_by_title('Test Album For Detached')
        assert album is not None
        _ = album.artist
        # Must not raise DetachedInstanceError and must actually be populated
        assert len(album.tracks) >= 1

    def test_get_all_relationships_accessible(
        self, album_repository, track_repository, session_factory
    ):
        """get_all() must return albums with accessible relationships (#4236)."""
        self._setup_album(track_repository, session_factory)

        albums, total = album_repository.get_all(limit=10)
        assert total >= 1
        for album in albums:
            _ = album.artist
            assert len(album.tracks) >= 0  # must not raise DetachedInstanceError

    def test_get_recent_relationships_accessible(
        self, album_repository, track_repository, session_factory
    ):
        """get_recent() must return albums with accessible relationships (#4236)."""
        self._setup_album(track_repository, session_factory)

        albums = album_repository.get_recent(limit=10)
        assert len(albums) >= 1
        for album in albums:
            _ = album.artist
            assert len(album.tracks) >= 0  # must not raise DetachedInstanceError

    def test_search_relationships_accessible(
        self, album_repository, track_repository, session_factory
    ):
        """search() must return albums with accessible relationships (#4236).

        Pre-existing bug fixed while touching this test: search() returns a
        (list, total) tuple, but the test previously assigned it directly to
        `albums` without unpacking, so `len(albums) >= 1` was trivially true
        on the 2-tuple and `for album in albums` iterated (list, int) rather
        than the actual album rows — the relationship-access assertions were
        never exercised.
        """
        self._setup_album(track_repository, session_factory)

        albums, total = album_repository.search('Test Album For Detached')
        assert total >= 1
        for album in albums:
            _ = album.artist
            assert len(album.tracks) >= 0  # must not raise DetachedInstanceError


class TestArtistRepositoryDetachedAccess:
    """Verify ArtistRepository methods return safely detached objects"""

    def _setup_artist(self, track_repository, session_factory):
        """Create a track with artist for testing"""
        return track_repository.add({
            'title': 'Artist Test Track',
            'filepath': '/tmp/artist_test.wav',
            'duration': 200.0,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'artists': ['Detached Test Artist'],
            'album': 'Artist Test Album',
        })

    def test_get_by_id_relationships_accessible(
        self, artist_repository, track_repository, session_factory
    ):
        """get_by_id() must return artist with accessible relationships"""
        track = self._setup_artist(track_repository, session_factory)
        assert track is not None
        artist_id = track.artists[0].id

        artist = artist_repository.get_by_id(artist_id)
        assert artist is not None
        _ = artist.tracks
        _ = artist.albums

    def test_get_by_name_relationships_accessible(
        self, artist_repository, track_repository, session_factory
    ):
        """get_by_name() must return artist with accessible relationships,
        including the NESTED artist.albums[i].tracks (fixes #4236 — sibling
        of get_by_id's nested selectinload(Artist.albums).selectinload(
        Album.tracks); get_by_name previously eager-loaded only the flat
        Artist.albums relationship, so .albums[i].tracks raised
        DetachedInstanceError)."""
        self._setup_artist(track_repository, session_factory)

        artist = artist_repository.get_by_name('Detached Test Artist')
        assert artist is not None
        _ = artist.tracks
        assert len(artist.albums) >= 1
        for album in artist.albums:
            # Must not raise DetachedInstanceError
            assert len(album.tracks) >= 0

    def test_get_all_relationships_accessible(
        self, artist_repository, track_repository, session_factory
    ):
        """get_all() must return artists with accessible relationships,
        including nested artist.albums[i].tracks (#4236 sibling fix)."""
        self._setup_artist(track_repository, session_factory)

        artists, total = artist_repository.get_all(limit=10)
        assert total >= 1
        for artist in artists:
            _ = artist.tracks
            for album in artist.albums:
                assert len(album.tracks) >= 0  # must not raise DetachedInstanceError

    def test_search_relationships_accessible(
        self, artist_repository, track_repository, session_factory
    ):
        """search() must return artists with accessible relationships,
        including nested artist.albums[i].tracks (#4236 sibling fix)."""
        self._setup_artist(track_repository, session_factory)

        artists, total = artist_repository.search('Detached Test')
        assert total >= 1
        for artist in artists:
            _ = artist.tracks
            for album in artist.albums:
                assert len(album.tracks) >= 0  # must not raise DetachedInstanceError


class TestSettingsRepositoryDetachedAccess:
    """Verify SettingsRepository methods return safely detached objects.

    UserSettings has no relationships (scalar columns only), so unlike the
    Track/Album/Artist suites above there is no lazy-loaded collection to
    exercise here. These assertions instead verify the returned object
    carries the actual values the operation was supposed to produce, not
    just a truthy id — `is not None` alone would pass even if the write
    silently no-op'd or returned a stale/wrong row (#4257).
    """

    def test_get_settings_accessible(self, settings_repository):
        """get_settings() must return an accessible object with real defaults"""
        settings = settings_repository.get_settings()
        assert settings is not None
        # Access attributes after session close, and confirm they're the
        # actual column defaults, not just present.
        assert settings.id is not None
        assert settings.volume == 0.8
        assert settings.theme == 'dark'

    def test_update_settings_accessible(self, settings_repository):
        """update_settings() must return an accessible object reflecting the write"""
        settings = settings_repository.update_settings({'volume': 0.35, 'theme': 'light'})
        assert settings is not None
        assert settings.volume == 0.35
        assert settings.theme == 'light'

    def test_reset_to_defaults_accessible(self, settings_repository):
        """reset_to_defaults() must return an accessible object with default values"""
        settings_repository.update_settings({'volume': 0.1, 'theme': 'light'})

        settings = settings_repository.reset_to_defaults()
        assert settings is not None
        assert settings.volume == 0.8
        assert settings.theme == 'dark'


class TestQueueRepositoryDetachedAccess:
    """Verify QueueRepository methods return safely detached objects.

    QueueState also has no relationships, so these assertions verify the
    returned object's actual field values rather than just its presence
    (#4257) — matching the rationale in TestSettingsRepositoryDetachedAccess.
    """

    def _get_queue_repo(self, repository_factory):
        return repository_factory.queue

    def test_get_queue_state_accessible(self, repository_factory):
        """get_queue_state() must return an accessible object with real defaults"""
        import json

        repo = self._get_queue_repo(repository_factory)
        state = repo.get_queue_state()
        assert state is not None
        assert state.id is not None
        assert json.loads(state.track_ids) == []
        assert state.current_index == 0

    def test_set_queue_state_accessible(self, repository_factory):
        """set_queue_state() must return an accessible object reflecting the write"""
        import json

        repo = self._get_queue_repo(repository_factory)
        state = repo.set_queue_state(track_ids=[1, 2, 3], current_index=1)
        assert state is not None
        assert json.loads(state.track_ids) == [1, 2, 3]
        assert state.current_index == 1

    def test_clear_queue_accessible(self, repository_factory):
        """clear_queue() must return an accessible object with the queue actually cleared"""
        import json

        repo = self._get_queue_repo(repository_factory)
        repo.set_queue_state(track_ids=[1, 2, 3], current_index=2)

        state = repo.clear_queue()
        assert state is not None
        assert json.loads(state.track_ids) == []
        assert state.current_index == 0
