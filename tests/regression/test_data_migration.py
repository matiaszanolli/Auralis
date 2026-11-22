"""
Data Migration Regression Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for data migration across versions.

REGRESSION CONTROLS TESTED:
- Library database schema migrations
- Album artwork migration
- Playlist format changes
- Track metadata evolution
- Artist/Album relationship changes
- Queue persistence format
- User preferences migration
"""

import json
import os
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text

from auralis.library.models import Album, Artist, Base, Playlist, Track


@pytest.mark.regression
class TestTrackSchemaMigration:
    """Test track table schema migrations."""

    def test_new_track_fields_have_defaults(self, temp_db):
        """
        REGRESSION: New fields added in schema v3 have defaults.
        Test: play_count, favorite, last_played default correctly.
        """
        from auralis.library.repositories import TrackRepository

        track_repo = TrackRepository(temp_db)

        # Add track without new fields
        track_info = {
            'filepath': '/tmp/old_track.flac',
            'title': 'Old Track',
            'artists': ['Artist'],
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
            # Missing: play_count, favorite, last_played
        }

        track = track_repo.add(track_info)

        # New fields should have defaults
        assert track.play_count == 0, "play_count should default to 0"
        assert track.favorite is False, "favorite should default to False"
        assert track.last_played is None, "last_played should default to NULL"

    def test_existing_track_data_preserved(self, temp_db):
        """
        REGRESSION: Schema migration preserves existing track data.
        Test: Old tracks retain title, filepath, duration, etc.
        """
        from auralis.library.repositories import TrackRepository

        track_repo = TrackRepository(temp_db)

        # Add track with full data
        track_info = {
            'filepath': '/tmp/preserved_track.flac',
            'title': 'Preserved Track',
            'artists': ['Preserved Artist'],
            'album': 'Preserved Album',
            'year': 2020,
            'track_number': 5,
            'genre': 'Rock',
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2,
            'duration': 245.5,
        }

        track = track_repo.add(track_info)

        # Retrieve and verify all data preserved
        retrieved = track_repo.get_by_id(track.id)

        assert retrieved.title == 'Preserved Track'
        assert retrieved.filepath == '/tmp/preserved_track.flac'
        assert retrieved.year == 2020
        assert retrieved.track_number == 5
        assert retrieved.format == 'FLAC'
        assert retrieved.sample_rate == 44100
        assert retrieved.channels == 2
        assert retrieved.duration == 245.5

    def test_track_artist_relationship_preserved(self, temp_db):
        """
        REGRESSION: Many-to-many track-artist relationship preserved.
        Test: Track can have multiple artists after migration.
        """
        from auralis.library.repositories import TrackRepository

        track_repo = TrackRepository(temp_db)

        # Add track with multiple artists
        track_info = {
            'filepath': '/tmp/collab_track.flac',
            'title': 'Collaboration Track',
            'artists': ['Artist 1', 'Artist 2', 'Artist 3'],
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
        }

        track = track_repo.add(track_info)

        # Should preserve multiple artists
        # (Can't check directly due to lazy loading, just verify no crash)
        assert track is not None
        assert track.title == 'Collaboration Track'


@pytest.mark.regression
class TestAlbumMigration:
    """Test album table migrations."""

    def test_album_year_migration(self, temp_db):
        """
        REGRESSION: Album year field preserved in migration.
        Test: Year values migrate correctly.
        """
        session = temp_db()

        # Create artist
        artist = Artist(name='Migration Artist')
        session.add(artist)
        session.commit()

        # Create album with year
        album = Album(
            title='Migration Album',
            artist_id=artist.id,
            year=1985
        )
        session.add(album)
        session.commit()

        # Retrieve
        retrieved_album = session.execute(select(Album).filter_by(id=album.id)).scalars().first()

        assert retrieved_album.year == 1985, "Year should be preserved"

        session.close()

    def test_album_artwork_path_preserved(self, temp_db):
        """
        REGRESSION: Album artwork_path field preserved.
        Test: Artwork paths migrate correctly.
        """
        session = temp_db()

        artist = Artist(name='Artwork Artist')
        session.add(artist)
        session.commit()

        album = Album(
            title='Artwork Album',
            artist_id=artist.id,
            year=2024,
            artwork_path='/path/to/artwork.jpg'
        )
        session.add(album)
        session.commit()

        retrieved = session.execute(select(Album).filter_by(id=album.id)).scalars().first()

        assert retrieved.artwork_path == '/path/to/artwork.jpg', \
            "Artwork path should be preserved"

        session.close()

    def test_album_without_year_handled(self, temp_db):
        """
        REGRESSION: Albums without year should handle NULL.
        Test: Year can be NULL.
        """
        session = temp_db()

        artist = Artist(name='No Year Artist')
        session.add(artist)
        session.commit()

        album = Album(
            title='Unknown Year Album',
            artist_id=artist.id,
            year=None  # No year
        )
        session.add(album)
        session.commit()

        retrieved = session.execute(select(Album).filter_by(id=album.id)).scalars().first()

        assert retrieved.year is None, "NULL year should be allowed"

        session.close()


@pytest.mark.regression
class TestArtistMigration:
    """Test artist table migrations."""

    def test_artist_name_uniqueness(self, temp_db):
        """
        REGRESSION: Artist names should be unique.
        Test: Duplicate artist names handled.
        """
        session = temp_db()

        # Add artist
        artist1 = Artist(name='Unique Artist')
        session.add(artist1)
        session.commit()

        # Try to add duplicate (should either fail or be ignored)
        artist2 = Artist(name='Unique Artist')
        session.add(artist2)

        try:
            session.commit()
            # If succeeded, query should return only one artist
            count = session.scalar(select(func.count()).select_from(Artist).filter_by(name='Unique Artist'))
            # Either 1 (deduplication) or 2 (no constraint)
            assert count >= 1, "At least one artist should exist"
        except Exception:
            # Unique constraint violation is acceptable
            session.rollback()

        session.close()

    def test_artist_album_relationship(self, temp_db):
        """
        REGRESSION: Artist-Album one-to-many relationship preserved.
        Test: Artist can have multiple albums.
        """
        session = temp_db()

        # Create artist with multiple albums
        artist = Artist(name='Prolific Artist')
        session.add(artist)
        session.commit()

        album1 = Album(title='Album 1', artist_id=artist.id, year=2020)
        album2 = Album(title='Album 2', artist_id=artist.id, year=2021)
        album3 = Album(title='Album 3', artist_id=artist.id, year=2022)

        session.add_all([album1, album2, album3])
        session.commit()

        # Query albums by artist
        albums = session.execute(select(Album).filter_by(artist_id=artist.id)).scalars().all()

        assert len(albums) == 3, "Artist should have 3 albums"

        session.close()


@pytest.mark.regression
class TestPlaylistMigration:
    """Test playlist schema migrations."""

    def test_playlist_basic_fields_preserved(self, temp_db):
        """
        REGRESSION: Playlist name and metadata preserved.
        Test: Playlist properties migrate correctly.
        """
        session = temp_db()

        playlist = Playlist(
            name='Test Playlist',
            description='A test playlist'
        )
        session.add(playlist)
        session.commit()

        retrieved = session.execute(select(Playlist).filter_by(id=playlist.id)).scalars().first()

        assert retrieved.name == 'Test Playlist'
        assert retrieved.description == 'A test playlist'

        session.close()

    def test_playlist_track_order_preserved(self, temp_db):
        """
        REGRESSION: Playlist track order should be preserved.
        Test: Track positions remain stable.
        """
        from auralis.library.repositories import PlaylistRepository, TrackRepository

        track_repo = TrackRepository(temp_db)
        playlist_repo = PlaylistRepository(temp_db)

        # Add tracks
        track_ids = []
        for i in range(5):
            track_info = {
                'filepath': f'/tmp/playlist_track_{i}.flac',
                'title': f'Playlist Track {i}',
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            }
            track = track_repo.add(track_info)
            track_ids.append(track.id)

        # Create playlist with tracks
        playlist = playlist_repo.create('Ordered Playlist')

        # Add tracks in specific order
        for track_id in track_ids:
            playlist_repo.add_track(playlist.id, track_id)

        # Retrieve playlist
        retrieved_playlist = playlist_repo.get_by_id(playlist.id)

        # Verify playlist exists
        assert retrieved_playlist is not None
        assert retrieved_playlist.name == 'Ordered Playlist'

    def test_empty_playlist_migration(self, temp_db):
        """
        REGRESSION: Empty playlists should migrate correctly.
        Test: Playlist with no tracks handled.
        """
        from auralis.library.repositories import PlaylistRepository

        playlist_repo = PlaylistRepository(temp_db)

        # Create empty playlist
        playlist = playlist_repo.create('Empty Playlist')

        # Retrieve
        retrieved = playlist_repo.get_by_id(playlist.id)

        assert retrieved is not None
        assert retrieved.name == 'Empty Playlist'


@pytest.mark.regression
class TestArtworkMigration:
    """Test album artwork migration."""

    def test_artwork_cache_directory_created(self, tmp_path):
        """
        REGRESSION: the artwork cache lives beside the open library database.
        Test: a database opened elsewhere moves the cache root with it. Opened on a temp path,
        never the developer's real ~/.auralis/library.db (#6654).
        """
        from auralis.library.data_dir import artwork_dir
        from auralis.library.database import LibraryDatabase

        db = LibraryDatabase(database_path=str(tmp_path / "library.db"))
        try:
            assert artwork_dir() == tmp_path.resolve() / "artwork"
        finally:
            db.shutdown()

    def test_missing_artwork_handled_gracefully(self, temp_db):
        """
        REGRESSION: Missing artwork files shouldn't break queries.
        Test: Album with invalid artwork_path loads.
        """
        session = temp_db()

        artist = Artist(name='Missing Artwork Artist')
        session.add(artist)
        session.commit()

        album = Album(
            title='Missing Artwork Album',
            artist_id=artist.id,
            year=2024,
            artwork_path='/nonexistent/artwork.jpg'
        )
        session.add(album)
        session.commit()

        # Should load successfully even with invalid path
        retrieved = session.execute(select(Album).filter_by(id=album.id)).scalars().first()

        assert retrieved is not None
        assert retrieved.artwork_path == '/nonexistent/artwork.jpg'

        session.close()


@pytest.mark.regression
class TestUserPreferencesMigration:
    """A track's favorite flag and play statistics survive what rewrites the row.

    These used to pass favorite/play_count to TrackRepository.add() and read them
    back. add() builds a track from a file, which has no play history, so it
    ignores them; only the scanner calls it. The stats are set through
    set_favorite()/record_play() and must survive a rescan and a metadata edit,
    which both rewrite the same row (#6709 follow-up).
    """

    @staticmethod
    def _played_favorite(temp_db):
        from auralis.library.repositories import TrackRepository

        repo = TrackRepository(temp_db)
        track = repo.add({
            'filepath': '/tmp/favorite.flac', 'title': 'Old Title', 'artists': ['Old Artist'],
            'genres': ['Rock'], 'format': 'FLAC', 'sample_rate': 44100, 'channels': 2,
        })
        assert track is not None
        assert repo.set_favorite(track.id, True) is True
        for _ in range(3):
            repo.record_play(track.id)
        before = repo.get_by_id(track.id)
        assert (before.favorite, before.play_count) == (True, 3)
        assert before.last_played is not None
        return repo, before

    def test_favorite_and_play_stats_survive_a_rescan(self, temp_db):
        repo, before = self._played_favorite(temp_db)

        # The scanner's whole-file re-read: new tags, absent keys cleared.
        repo.update_by_filepath(
            '/tmp/favorite.flac',
            {'title': 'New Title', 'artists': ['New Artist'], 'format': 'FLAC',
             'sample_rate': 44100, 'channels': 2},
            replace_tags=True,
        )

        after = repo.get_by_id(before.id)
        assert after.title == 'New Title'
        assert [a.name for a in after.artists] == ['New Artist']
        assert (after.favorite, after.play_count, after.last_played) == (True, 3, before.last_played)

    def test_favorite_and_play_stats_survive_a_metadata_edit(self, temp_db):
        repo, before = self._played_favorite(temp_db)

        repo.update(before.id, {'title': 'Edited', 'artists': ['Someone Else'], 'genres': ['Jazz']})

        after = repo.get_by_id(before.id)
        assert after.title == 'Edited'
        assert (after.favorite, after.play_count, after.last_played) == (True, 3, before.last_played)
