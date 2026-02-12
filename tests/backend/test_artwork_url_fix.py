"""
Tests for Artwork URL Fix (#2107)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests that artwork_path is returned as API URL instead of filesystem path.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add auralis to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.library.models import Album, Artist, Base, Track


class TestAlbumArtworkURL:
    """Test Album.to_dict() returns artwork URLs instead of filesystem paths"""

    @pytest.fixture
    def db_session(self):
        """Create an in-memory database session for testing"""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    def test_album_with_artwork_path_returns_url(self, db_session):
        """Test that album with artwork_path returns API URL, not filesystem path"""
        # Create album with artwork_path
        album = Album(
            id=123,
            title="Test Album",
            artwork_path="/home/user/.auralis/artwork/album_123_abc.jpg"
        )
        db_session.add(album)
        db_session.commit()

        # Convert to dict
        album_dict = album.to_dict()

        # Should return URL, not filesystem path
        assert album_dict['artwork_path'] == "/api/albums/123/artwork"
        assert not album_dict['artwork_path'].startswith("/home/")
        assert not album_dict['artwork_path'].endswith(".jpg")

    def test_album_without_artwork_returns_none(self, db_session):
        """Test that album without artwork_path returns None"""
        # Create album without artwork
        album = Album(
            id=456,
            title="Album Without Artwork",
            artwork_path=None
        )
        db_session.add(album)
        db_session.commit()

        # Convert to dict
        album_dict = album.to_dict()

        # Should return None
        assert album_dict['artwork_path'] is None

    def test_album_with_empty_artwork_returns_none(self, db_session):
        """Test that album with empty artwork_path returns None"""
        # Create album with empty artwork
        album = Album(
            id=789,
            title="Album With Empty Artwork",
            artwork_path=""
        )
        db_session.add(album)
        db_session.commit()

        # Convert to dict
        album_dict = album.to_dict()

        # Empty string should result in None
        assert album_dict['artwork_path'] is None


class TestTrackArtworkURL:
    """Test Track.to_dict() returns album artwork URLs instead of filesystem paths"""

    @pytest.fixture
    def db_session(self):
        """Create an in-memory database session for testing"""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    def test_track_with_album_artwork_returns_url(self, db_session):
        """Test that track with album artwork returns API URL"""
        # Create album with artwork
        album = Album(
            id=100,
            title="Album with Artwork",
            artwork_path="/home/user/.auralis/artwork/album_100_xyz.jpg"
        )
        db_session.add(album)
        db_session.flush()

        # Create track linked to album
        track = Track(
            id=1,
            title="Test Track",
            filepath="/music/track.mp3",
            album_id=album.id,
            duration=180.0
        )
        db_session.add(track)
        db_session.commit()

        # Refresh to load relationship
        db_session.refresh(track)

        # Convert to dict
        track_dict = track.to_dict()

        # Should return URL, not filesystem path
        assert track_dict['album_art'] == "/api/albums/100/artwork"
        assert not track_dict['album_art'].startswith("/home/")
        assert not track_dict['album_art'].endswith(".jpg")

    def test_track_without_album_returns_none(self, db_session):
        """Test that track without album returns None for album_art"""
        # Create track without album
        track = Track(
            id=2,
            title="Orphan Track",
            filepath="/music/orphan.mp3",
            duration=120.0
        )
        db_session.add(track)
        db_session.commit()

        # Convert to dict
        track_dict = track.to_dict()

        # Should return None
        assert track_dict['album_art'] is None

    def test_track_with_album_without_artwork_returns_none(self, db_session):
        """Test that track with album but no artwork returns None"""
        # Create album without artwork
        album = Album(
            id=200,
            title="Album Without Artwork",
            artwork_path=None
        )
        db_session.add(album)
        db_session.flush()

        # Create track linked to album
        track = Track(
            id=3,
            title="Track Without Art",
            filepath="/music/noart.mp3",
            album_id=album.id,
            duration=200.0
        )
        db_session.add(track)
        db_session.commit()

        # Refresh to load relationship
        db_session.refresh(track)

        # Convert to dict
        track_dict = track.to_dict()

        # Should return None
        assert track_dict['album_art'] is None


class TestArtworkURLSecurity:
    """Test that artwork URLs don't leak filesystem information"""

    @pytest.fixture
    def db_session(self):
        """Create an in-memory database session for testing"""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    def test_no_filesystem_paths_in_album_dict(self, db_session):
        """Test that Album.to_dict() doesn't expose filesystem paths"""
        # Create album with artwork path containing sensitive info
        album = Album(
            id=999,
            title="Sensitive Album",
            artwork_path="/home/admin/.auralis/artwork/secret_album_999.jpg"
        )
        db_session.add(album)
        db_session.commit()

        # Convert to dict
        album_dict = album.to_dict()

        # Check all values don't contain filesystem markers
        for key, value in album_dict.items():
            if isinstance(value, str):
                assert not value.startswith("/home/"), f"Field {key} leaks filesystem path"
                assert not value.startswith("/Users/"), f"Field {key} leaks filesystem path"
                assert not value.startswith("C:\\"), f"Field {key} leaks filesystem path"
                assert ".auralis" not in value, f"Field {key} leaks internal directory"

    def test_no_filesystem_paths_in_track_dict(self, db_session):
        """Test that Track.to_dict() doesn't expose artwork filesystem paths"""
        # Create album with artwork
        album = Album(
            id=888,
            title="Test Album",
            artwork_path="/home/user/.auralis/artwork/album_888.jpg"
        )
        db_session.add(album)
        db_session.flush()

        # Create track
        track = Track(
            id=10,
            title="Test Track",
            filepath="/music/test.mp3",  # This is OK - it's the music file path
            album_id=album.id,
            duration=150.0
        )
        db_session.add(track)
        db_session.commit()

        # Refresh to load relationship
        db_session.refresh(track)

        # Convert to dict
        track_dict = track.to_dict()

        # album_art should not contain .auralis or filesystem artwork path
        if track_dict['album_art']:
            assert ".auralis" not in track_dict['album_art']
            assert track_dict['album_art'].startswith("/api/")

    def test_url_format_is_correct(self, db_session):
        """Test that generated URLs follow correct format"""
        album = Album(
            id=777,
            title="URL Format Test",
            artwork_path="/some/path/artwork.jpg"
        )
        db_session.add(album)
        db_session.commit()

        album_dict = album.to_dict()

        # URL should be exactly: /api/albums/{id}/artwork
        expected_url = "/api/albums/777/artwork"
        assert album_dict['artwork_path'] == expected_url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
