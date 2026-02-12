"""
Tests for Track Artwork Field Naming Consistency (#2109)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests that track artwork uses consistent field naming across all layers.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add auralis to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.library.models import Album, Base, Track


class TestTrackArtworkFieldNaming:
    """Test Track.to_dict() uses consistent field naming"""

    @pytest.fixture
    def db_session(self):
        """Create an in-memory database session for testing"""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    def test_track_uses_artwork_url_not_album_art(self, db_session):
        """Test that track dict uses 'artwork_url', not 'album_art'"""
        # Create album with artwork
        album = Album(
            id=100,
            title="Test Album",
            artwork_path="/home/user/.auralis/artwork/album_100.jpg"
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

        # Should use 'artwork_url', not 'album_art'
        assert 'artwork_url' in track_dict, "Track dict should have 'artwork_url' field"
        assert 'album_art' not in track_dict, "Track dict should NOT have 'album_art' field (deprecated)"

        # Value should be artwork URL
        assert track_dict['artwork_url'] == "/api/albums/100/artwork"

    def test_track_without_artwork_returns_none(self, db_session):
        """Test that track without artwork has None for artwork_url"""
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
            id=2,
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

        # Should have artwork_url field with None value
        assert 'artwork_url' in track_dict
        assert track_dict['artwork_url'] is None

    def test_orphan_track_returns_none_artwork(self, db_session):
        """Test that track without album has None for artwork_url"""
        # Create track without album
        track = Track(
            id=3,
            title="Orphan Track",
            filepath="/music/orphan.mp3",
            duration=120.0
        )
        db_session.add(track)
        db_session.commit()

        # Convert to dict
        track_dict = track.to_dict()

        # Should have artwork_url field with None value
        assert 'artwork_url' in track_dict
        assert track_dict['artwork_url'] is None


class TestFieldNamingConsistency:
    """Test field naming consistency across the API"""

    @pytest.fixture
    def db_session(self):
        """Create an in-memory database session for testing"""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    def test_no_deprecated_field_names_in_track_dict(self, db_session):
        """Test that track dict doesn't contain deprecated field names"""
        # Create album with artwork
        album = Album(
            id=300,
            title="Test Album",
            artwork_path="/home/user/.auralis/artwork/album_300.jpg"
        )
        db_session.add(album)
        db_session.flush()

        # Create track
        track = Track(
            id=10,
            title="Test Track",
            filepath="/music/test.mp3",
            album_id=album.id,
            duration=150.0
        )
        db_session.add(track)
        db_session.commit()

        # Refresh to load relationship
        db_session.refresh(track)

        # Convert to dict
        track_dict = track.to_dict()

        # Check for deprecated field names
        deprecated_fields = ['album_art', 'cover_url', 'coverUrl', 'albumArt']
        for deprecated_field in deprecated_fields:
            assert deprecated_field not in track_dict, \
                f"Track dict should not contain deprecated field '{deprecated_field}'"

    def test_artwork_url_is_api_url_not_filesystem_path(self, db_session):
        """Test that artwork_url contains API URL, not filesystem path"""
        # Create album with artwork
        album = Album(
            id=400,
            title="Test Album",
            artwork_path="/home/user/.auralis/artwork/album_400.jpg"
        )
        db_session.add(album)
        db_session.flush()

        # Create track
        track = Track(
            id=20,
            title="Test Track",
            filepath="/music/test.mp3",
            album_id=album.id,
            duration=150.0
        )
        db_session.add(track)
        db_session.commit()

        # Refresh to load relationship
        db_session.refresh(track)

        # Convert to dict
        track_dict = track.to_dict()

        # Should be API URL
        assert track_dict['artwork_url'].startswith("/api/albums/")
        assert track_dict['artwork_url'].endswith("/artwork")

        # Should not be filesystem path
        assert not track_dict['artwork_url'].startswith("/home/")
        assert ".auralis" not in track_dict['artwork_url']

    def test_field_name_snake_case_at_api_boundary(self, db_session):
        """Test that field name is snake_case at API boundary (Python side)"""
        # Create album with artwork
        album = Album(
            id=500,
            title="Test Album",
            artwork_path="/home/user/.auralis/artwork/album_500.jpg"
        )
        db_session.add(album)
        db_session.flush()

        # Create track
        track = Track(
            id=30,
            title="Test Track",
            filepath="/music/test.mp3",
            album_id=album.id,
            duration=150.0
        )
        db_session.add(track)
        db_session.commit()

        # Refresh to load relationship
        db_session.refresh(track)

        # Convert to dict
        track_dict = track.to_dict()

        # API boundary uses snake_case (Python convention)
        assert 'artwork_url' in track_dict  # snake_case
        assert 'artworkUrl' not in track_dict  # camelCase is frontend only


class TestAPIContractCompliance:
    """Test compliance with API contract defined in frontend types"""

    @pytest.fixture
    def db_session(self):
        """Create an in-memory database session for testing"""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    def test_track_dict_matches_TrackApiResponse_contract(self, db_session):
        """Test that Track.to_dict() matches TrackApiResponse interface"""
        # Create album with artwork
        album = Album(
            id=600,
            title="Test Album",
            artwork_path="/some/path/artwork.jpg"
        )
        db_session.add(album)
        db_session.flush()

        # Create track with all fields
        track = Track(
            id=40,
            title="Full Track",
            filepath="/music/full.mp3",
            album_id=album.id,
            duration=200.0,
            sample_rate=44100,
            bit_depth=16,
            format="MP3"
        )
        db_session.add(track)
        db_session.commit()

        # Refresh to load relationship
        db_session.refresh(track)

        # Convert to dict
        track_dict = track.to_dict()

        # TrackApiResponse expects these snake_case fields
        # Note: Track model returns 'artists' (plural list), not 'artist' (singular)
        expected_fields = [
            'id', 'title', 'album', 'duration', 'filepath',
            'artwork_url',  # KEY FIELD - standardized name
            'sample_rate', 'bit_depth', 'format',
            'artists'  # plural list of artist names
        ]

        for field in expected_fields:
            assert field in track_dict or f"{field} (optional)" in str(track_dict.keys()), \
                f"Track dict missing required field '{field}' from TrackApiResponse contract"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
