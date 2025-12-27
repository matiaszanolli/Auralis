"""
SQL Injection Prevention Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests to verify that the system is protected against SQL injection attacks.

The system uses SQLAlchemy ORM which provides automatic protection through
parameterized queries. These tests verify that malicious SQL cannot be
injected through user inputs.
"""

import sys
from pathlib import Path

import pytest

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from auralis.library.models import Album, Artist, Track
from auralis.library.repositories import (
    AlbumRepository,
    ArtistRepository,
    TrackRepository,
)
from tests.security.helpers import is_sql_injection


@pytest.mark.security
@pytest.mark.integration
class TestSQLInjectionPrevention:
    """Test suite for SQL injection prevention."""

    def test_search_query_sql_injection(self, temp_db, malicious_inputs):
        """
        Test SQL injection in search queries.

        Verifies that malicious SQL in search terms cannot:
        - Drop tables
        - Access unauthorized data
        - Modify database structure
        - Execute arbitrary SQL
        """
        repo = TrackRepository(temp_db)
        session = temp_db()

        # Create test data
        artist = Artist(name="Test Artist")
        session.add(artist)
        session.flush()

        album = Album(title="Test Album", artist_id=artist.id)
        session.add(album)
        session.flush()

        track = Track(
            filepath="/test/safe.mp3",
            title="Safe Track",
            duration=180.0,
            album_id=album.id
        )
        session.add(track)
        session.commit()

        # Try SQL injection patterns in search
        for sql_injection in malicious_inputs['sql_injection']:
            # Search should not execute SQL, just return empty or safe results
            results, total = repo.search(sql_injection)

            # Verify no SQL was executed
            # 1. Table still exists (wasn't dropped)
            count = session.query(Track).count()
            assert count == 1, f"Table altered by injection: {sql_injection}"

            # 2. Search returns safe results (empty or legitimate matches)
            assert isinstance(results, list), "Search should return list"
            assert isinstance(total, int), "Total should be int"
            for result in results:
                assert isinstance(result, Track), "Results should be Track objects"

        session.close()

    def test_metadata_field_sql_injection(self, temp_db, malicious_inputs):
        """
        Test SQL injection in metadata fields.

        Verifies that malicious SQL in track metadata cannot:
        - Modify other records
        - Access unauthorized data
        - Execute stored in database as literal strings
        """
        repo = TrackRepository(temp_db)
        session = temp_db()

        # Create artist and album
        artist = Artist(name="Test Artist")
        session.add(artist)
        session.flush()

        album = Album(title="Test Album", artist_id=artist.id)
        session.add(album)
        session.flush()

        # Try injecting SQL into various metadata fields
        for i, sql_injection in enumerate(malicious_inputs['sql_injection']):
            track = Track(
                filepath=f"/test/track_{i}.mp3",
                title=sql_injection,  # Injection attempt in title
                duration=180.0,
                album_id=album.id
            )
            session.add(track)

        session.commit()

        # Verify all tracks were stored safely
        tracks = session.query(Track).all()
        assert len(tracks) == len(malicious_inputs['sql_injection'])

        # Verify SQL was stored as literal string, not executed
        for track in tracks:
            # Title should contain the SQL as text
            assert is_sql_injection(track.title), "SQL injection pattern stored as text"

            # Verify track has valid ID (wasn't corrupted)
            assert track.id > 0

        session.close()

    def test_parameterized_queries(self, temp_db):
        """
        Test that ORM uses parameterized queries.

        Verifies that SQLAlchemy ORM properly parameterizes all queries,
        preventing SQL injection at the database driver level.
        """
        session = temp_db()
        repo = TrackRepository(session)

        # Create test data
        artist = Artist(name="Test Artist")
        session.add(artist)
        session.flush()

        album = Album(title="Test Album", artist_id=artist.id)
        session.add(album)
        session.flush()

        track = Track(
            filepath="/test/safe.mp3",
            title="Safe Track",
            duration=180.0,
            album_id=album.id
        )
        session.add(track)
        session.commit()

        # Attempt injection through filter conditions
        malicious_title = "' OR '1'='1"

        # This should return no results (not bypass the WHERE clause)
        results = session.query(Track).filter(Track.title == malicious_title).all()
        assert len(results) == 0, "Parameterized query prevented injection"

        # Verify original data intact
        all_tracks = session.query(Track).all()
        assert len(all_tracks) == 1
        assert all_tracks[0].title == "Safe Track"

        session.close()

    def test_orm_level_protection(self, temp_db, malicious_inputs):
        """
        Test ORM-level SQL injection protection.

        Verifies that SQLAlchemy ORM prevents SQL injection through:
        - Automatic escaping
        - Parameterized queries
        - Type coercion
        """
        session = temp_db()

        # Create artist with injection attempt
        artist = Artist(name=malicious_inputs['sql_injection'][0])
        session.add(artist)
        session.flush()

        # Artist should be created with SQL as literal name
        assert artist.id > 0
        assert artist.name == malicious_inputs['sql_injection'][0]

        # Create album with injection attempt
        album = Album(
            title=malicious_inputs['sql_injection'][1],
            artist_id=artist.id
        )
        session.add(album)
        session.flush()

        # Album should be created with SQL as literal title
        assert album.id > 0
        assert album.title == malicious_inputs['sql_injection'][1]

        session.commit()

        # Verify database integrity
        artist_count = session.query(Artist).count()
        album_count = session.query(Album).count()

        assert artist_count == 1, "Only one artist created"
        assert album_count == 1, "Only one album created"

        session.close()

    def test_union_based_injection_attempts(self, temp_db, malicious_inputs):
        """
        Test UNION-based SQL injection attempts.

        Verifies that UNION attacks cannot:
        - Combine results from multiple tables
        - Access unauthorized data
        - Bypass access controls
        """
        repo = TrackRepository(temp_db)
        session = temp_db()

        # Create test data
        artist = Artist(name="Test Artist")
        session.add(artist)
        session.flush()

        album = Album(title="Test Album", artist_id=artist.id)
        session.add(album)
        session.flush()

        track = Track(
            filepath="/test/safe.mp3",
            title="Safe Track",
            duration=180.0,
            album_id=album.id
        )
        session.add(track)
        session.commit()

        # Attempt UNION-based injection
        union_injection = "' UNION SELECT * FROM tracks--"

        # Search with UNION injection
        results, total = repo.search(union_injection)

        # Verify no UNION was executed
        # Should return empty or safe results, not combined data
        assert isinstance(results, list)
        assert isinstance(total, int)

        # Verify we only get Track objects (not raw SQL results)
        for result in results:
            assert isinstance(result, Track)
            # Verify result has expected attributes
            assert hasattr(result, 'title')
            assert hasattr(result, 'filepath')
            assert hasattr(result, 'duration')

        # Verify database structure intact
        track_count = session.query(Track).count()
        assert track_count == 1, "No additional records from UNION"

        session.close()
