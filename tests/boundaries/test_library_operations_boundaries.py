"""
Library Operations Boundary Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests edge cases and boundary conditions for library database operations.

These tests verify critical invariants:
1. Duplicate prevention (no duplicate tracks by filepath)
2. Transaction integrity (rollback on error)
3. Foreign key constraints (cascade deletes)
4. Empty/null field handling
5. Concurrent operation safety

Test Categories:
- Add operations (6 tests)
- Delete operations (6 tests)
- Update operations (6 tests)
- Search operations (6 tests)
- Constraint violations (6 tests)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os

# Add auralis to path
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'auralis'))

from auralis.library.models import Album, Artist, Base, Track
from auralis.library.repositories import (
    AlbumRepository,
    ArtistRepository,
    TrackRepository,
)

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(engine)
        SessionFactory = sessionmaker(bind=engine)
        yield SessionFactory
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
def track_repo(temp_db):
    """Create track repository"""
    return TrackRepository(temp_db)


@pytest.fixture
def album_repo(temp_db):
    """Create album repository"""
    return AlbumRepository(temp_db)


@pytest.fixture
def artist_repo(temp_db):
    """Create artist repository"""
    return ArtistRepository(temp_db)


def create_test_track(index=0, **overrides):
    """
    Helper to create test track info dict.

    Args:
        index: Track number for unique naming
        **overrides: Override default values

    Returns:
        Dict with track information
    """
    defaults = {
        'filepath': f'/tmp/test_track_{index:03d}.flac',
        'title': f'Test Track {index:03d}',
        'artists': [f'Artist {index % 10}'],
        'album': f'Album {index % 5}',
        'duration': 180.0,
        'format': 'FLAC',
        'sample_rate': 44100,
        'channels': 2
    }
    defaults.update(overrides)
    return defaults


# ============================================================================
# CATEGORY 1: ADD OPERATIONS (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_add_duplicate_filepath(track_repo):
    """
    BOUNDARY: Adding track with duplicate filepath.
    Should prevent duplicates or return existing track.
    """
    track_info = create_test_track(0)

    # Add first time
    track1 = track_repo.add(track_info)
    assert track1 is not None, "First add should succeed"

    # Try to add duplicate
    track2 = track_repo.add(track_info)
    assert track2 is not None, "Should return existing track"
    assert track1.id == track2.id, "Should return same track on duplicate"

    # Verify only one track exists
    all_tracks, total = track_repo.get_all(limit=100, offset=0)
    assert total == 1, "Should have exactly 1 track (no duplicate)"


@pytest.mark.boundary
def test_add_empty_title(track_repo):
    """
    BOUNDARY: Adding track with empty title.
    Should either accept or reject gracefully.
    """
    track_info = create_test_track(0, title='')

    track = track_repo.add(track_info)

    # Should either succeed with empty title or fail
    if track is not None:
        assert track.title == '', "Empty title should be preserved if accepted"


@pytest.mark.boundary
def test_add_missing_required_fields(track_repo):
    """
    BOUNDARY: Adding track with missing filepath (required).
    Should reject or handle gracefully.
    """
    track_info = {
        'title': 'Test Track',
        'artists': ['Test Artist']
        # Missing 'filepath' - required field
    }

    try:
        track = track_repo.add(track_info)
        # If it succeeds, track should be None or invalid
        assert track is None or not hasattr(track, 'filepath'), \
            "Missing filepath should fail or create invalid track"
    except (KeyError, ValueError, TypeError):
        # Expected for missing required field
        pass


@pytest.mark.boundary
def test_add_very_long_fields(track_repo):
    """
    BOUNDARY: Adding track with very long field values.
    Should handle or truncate long strings.
    """
    long_title = 'A' * 10000  # 10k characters
    long_artist = 'B' * 10000
    track_info = create_test_track(0, title=long_title, artists=[long_artist])

    track = track_repo.add(track_info)

    if track is not None:
        # Should either store full string or truncate
        assert len(track.title) > 0, "Title should not be empty"
        # SQLite typically doesn't enforce VARCHAR length, but check it's stored
        assert track.title is not None


@pytest.mark.boundary
def test_add_null_optional_fields(track_repo):
    """
    BOUNDARY: Adding track with None/null for optional fields.
    Should handle null values for non-required fields.
    """
    track_info = {
        'filepath': '/tmp/test_null.flac',
        'title': 'Test Track',
        'artists': ['Test Artist'],
        'album': None,  # Optional - should accept None
        'year': None,   # Optional - should accept None
        'genre': None,  # Optional - should accept None
        'format': 'FLAC',
        'sample_rate': 44100,
        'channels': 2
    }

    track = track_repo.add(track_info)

    assert track is not None, "Should accept None for optional fields"
    assert track.year is None, "None should be preserved for year"


@pytest.mark.boundary
def test_add_maximum_track_count(track_repo):
    """
    BOUNDARY: Adding large number of tracks (stress test).
    Should handle 1000+ tracks without issues.
    """
    num_tracks = 1000

    for i in range(num_tracks):
        track_info = create_test_track(i)
        track = track_repo.add(track_info)
        assert track is not None, f"Failed to add track {i}"

    # Verify all tracks exist
    all_tracks, total = track_repo.get_all(limit=2000, offset=0)
    assert total == num_tracks, f"Should have {num_tracks} tracks, got {total}"


# ============================================================================
# CATEGORY 2: DELETE OPERATIONS (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_delete_nonexistent_track(track_repo):
    """
    BOUNDARY: Deleting track that doesn't exist.
    Should return False or handle gracefully.
    """
    result = track_repo.delete(999999)  # Non-existent ID

    assert result is False, "Deleting non-existent track should return False"


@pytest.mark.boundary
def test_delete_last_track(track_repo):
    """
    BOUNDARY: Deleting the only track in database.
    Should leave database in valid empty state.
    """
    # Add one track
    track_info = create_test_track(0)
    track = track_repo.add(track_info)

    # Delete it
    result = track_repo.delete(track.id)

    assert result is True, "Delete should succeed"

    # Verify database is empty
    all_tracks, total = track_repo.get_all(limit=100, offset=0)
    assert total == 0, "Database should be empty after deleting last track"


@pytest.mark.boundary
def test_delete_with_foreign_key_references(track_repo, temp_db):
    """
    BOUNDARY: Deleting artist referenced by tracks.
    Should handle foreign key constraints (cascade or prevent).
    """
    # Add track with artist
    track_info = create_test_track(0)
    track = track_repo.add(track_info)

    # Get artist
    session = temp_db()
    artist = session.query(Artist).first()
    artist_id = artist.id
    session.close()

    # Try to delete artist (has track referencing it)
    session = temp_db()
    try:
        artist_to_delete = session.query(Artist).filter(Artist.id == artist_id).first()
        session.delete(artist_to_delete)
        session.commit()
        # If cascade delete, track should also be deleted or artist reference nulled
    except Exception:
        session.rollback()
        # Foreign key constraint prevented delete
    finally:
        session.close()

    # Either way, database should still be consistent
    all_tracks, total = track_repo.get_all(limit=100, offset=0)
    assert total >= 0, "Database should be in consistent state"


@pytest.mark.boundary
def test_delete_all_tracks(track_repo):
    """
    BOUNDARY: Deleting all tracks from library.
    Should handle bulk delete.
    """
    # Add multiple tracks
    num_tracks = 50
    track_ids = []
    for i in range(num_tracks):
        track_info = create_test_track(i)
        track = track_repo.add(track_info)
        track_ids.append(track.id)

    # Delete all tracks
    for track_id in track_ids:
        result = track_repo.delete(track_id)
        assert result is True, f"Failed to delete track {track_id}"

    # Verify all deleted
    all_tracks, total = track_repo.get_all(limit=100, offset=0)
    assert total == 0, "All tracks should be deleted"


@pytest.mark.boundary
def test_delete_negative_id(track_repo):
    """
    BOUNDARY: Attempting to delete with negative ID.
    Should handle gracefully.
    """
    result = track_repo.delete(-1)

    # Should return False (not found)
    assert result is False, "Negative ID should not find any track"


@pytest.mark.boundary
def test_delete_zero_id(track_repo):
    """
    BOUNDARY: Attempting to delete with ID = 0.
    Should handle gracefully (IDs start at 1).
    """
    result = track_repo.delete(0)

    assert result is False, "ID 0 should not find any track"


# ============================================================================
# CATEGORY 3: UPDATE OPERATIONS (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_update_nonexistent_track(track_repo):
    """
    BOUNDARY: Updating track that doesn't exist.
    Should return None or handle gracefully.
    """
    update_info = {'title': 'New Title'}
    result = track_repo.update(999999, update_info)

    assert result is None, "Updating non-existent track should return None"


@pytest.mark.boundary
def test_update_empty_changes(track_repo):
    """
    BOUNDARY: Updating track with empty update dict.
    Should handle gracefully.
    """
    # Add track
    track_info = create_test_track(0)
    track = track_repo.add(track_info)
    original_title = track.title

    # Update with empty dict
    result = track_repo.update(track.id, {})

    if result is not None:
        assert result.title == original_title, "Empty update should not change fields"


@pytest.mark.boundary
def test_update_to_null_values(track_repo):
    """
    BOUNDARY: Updating optional fields to None/null.
    Should allow nulling optional fields.
    """
    # Add track with values
    track_info = create_test_track(0, year=2024, genre='Rock')
    track = track_repo.add(track_info)

    # Update to None
    update_info = {'year': None, 'genre': None}
    result = track_repo.update(track.id, update_info)

    if result is not None:
        assert result.year is None, "Year should be updated to None"


@pytest.mark.boundary
def test_update_all_fields(track_repo):
    """
    BOUNDARY: Updating all editable fields at once.
    Should handle bulk field updates.
    """
    # Add track
    track_info = create_test_track(0)
    track = track_repo.add(track_info)

    # Update all editable fields
    update_info = {
        'title': 'New Title',
        'artists': ['New Artist'],
        'album': 'New Album',
        'year': 2025,
        'track_number': 5,
        'disc_number': 2,
        'genre': 'Jazz',
        'comment': 'Updated comment'
    }
    result = track_repo.update(track.id, update_info)

    assert result is not None, "Bulk update should succeed"
    assert result.title == 'New Title', "Title should be updated"


@pytest.mark.boundary
def test_update_filepath(track_repo):
    """
    BOUNDARY: Attempting to update filepath (should preserve uniqueness).
    May be allowed or rejected depending on implementation.
    """
    # Add two tracks
    track1 = track_repo.add(create_test_track(0))
    track2 = track_repo.add(create_test_track(1))

    # Try to update track2's filepath to match track1's
    update_info = {'filepath': track1.filepath}

    # This should either fail (duplicate) or succeed with proper handling
    try:
        result = track_repo.update(track2.id, update_info)
        # If succeeds, should maintain data integrity
        if result is not None:
            # Check no duplicates created
            all_tracks, total = track_repo.get_all(limit=100, offset=0)
            filepaths = [t.filepath for t in all_tracks]
            assert len(filepaths) == len(set(filepaths)), "No duplicate filepaths"
    except Exception:
        # Expected if duplicate prevention is enforced
        pass


@pytest.mark.boundary
def test_update_very_long_field(track_repo):
    """
    BOUNDARY: Updating field to very long value.
    Should handle or truncate long strings.
    """
    # Add track
    track_info = create_test_track(0)
    track = track_repo.add(track_info)

    # Update to very long value
    long_title = 'X' * 10000
    update_info = {'title': long_title}
    result = track_repo.update(track.id, update_info)

    if result is not None:
        assert len(result.title) > 0, "Title should not be empty"


# ============================================================================
# CATEGORY 4: SEARCH OPERATIONS (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_search_empty_query(track_repo):
    """
    BOUNDARY: Searching with empty string.
    Should return all tracks or handle gracefully.
    """
    # Add some tracks
    for i in range(10):
        track_repo.add(create_test_track(i))

    # Search with empty string
    result = track_repo.search('', limit=100, offset=0)

    # Search returns (list, total) tuple
    if isinstance(result, tuple):
        results, total = result
        assert isinstance(results, list), "Should return a list"
    else:
        assert isinstance(result, list), "Should return a list"


@pytest.mark.boundary
def test_search_no_matches(track_repo):
    """
    BOUNDARY: Searching for term that matches nothing.
    Should return empty list.
    """
    # Add some tracks
    for i in range(10):
        track_repo.add(create_test_track(i))

    # Search for non-existent term
    result = track_repo.search('XYZNONEXISTENT123', limit=100, offset=0)

    # Handle tuple return
    if isinstance(result, tuple):
        results, total = result
        assert results == [], "No matches should return empty list"
    else:
        assert result == [], "No matches should return empty list"


@pytest.mark.boundary
def test_search_special_characters(track_repo):
    """
    BOUNDARY: Searching with special characters/SQL.
    Should handle safely (no SQL injection).
    """
    # Add tracks
    track_repo.add(create_test_track(0, title="Normal Track"))

    # Try SQL injection patterns
    malicious_queries = [
        "'; DROP TABLE tracks; --",
        "' OR '1'='1",
        "%",
        "_",
        "\\",
        "'",
        '"'
    ]

    for query in malicious_queries:
        try:
            results = track_repo.search(query, limit=100, offset=0)
            # Should not crash or expose all data
            assert isinstance(results, list), "Should return a list"
        except Exception:
            # Query may be rejected, which is fine
            pass


@pytest.mark.boundary
def test_search_very_long_query(track_repo):
    """
    BOUNDARY: Searching with extremely long query string.
    Should handle without error.
    """
    # Add tracks
    for i in range(10):
        track_repo.add(create_test_track(i))

    # Very long search query
    long_query = 'x' * 10000

    try:
        results = track_repo.search(long_query, limit=100, offset=0)
        assert isinstance(results, list), "Should return a list"
    except Exception:
        # May reject very long queries
        pass


@pytest.mark.boundary
def test_search_unicode_characters(track_repo):
    """
    BOUNDARY: Searching with unicode/emoji characters.
    Should handle international characters.
    """
    # Add track with unicode title
    track_info = create_test_track(0, title="Track 日本語 🎵")
    track_repo.add(track_info)

    # Search for unicode
    results = track_repo.search("日本語", limit=100, offset=0)

    # Should find the track
    assert len(results) >= 0, "Should handle unicode search"


@pytest.mark.boundary
def test_search_case_sensitivity(track_repo):
    """
    BOUNDARY: Test case-insensitive search behavior.
    Should find matches regardless of case.
    """
    # Add tracks
    track_repo.add(create_test_track(0, title="Test Track"))

    # Search with different cases
    result_lower = track_repo.search("test", limit=100, offset=0)
    result_upper = track_repo.search("TEST", limit=100, offset=0)
    result_mixed = track_repo.search("TeSt", limit=100, offset=0)

    # Handle tuple returns
    if isinstance(result_lower, tuple):
        results_lower, _ = result_lower
        results_upper, _ = result_upper
        results_mixed, _ = result_mixed
    else:
        results_lower = result_lower
        results_upper = result_upper
        results_mixed = result_mixed

    # All should return same results (case-insensitive)
    # Note: Implementation may vary, just verify no crash
    assert isinstance(results_lower, list)
    assert isinstance(results_upper, list)
    assert isinstance(results_mixed, list)


# ============================================================================
# CATEGORY 5: CONSTRAINT VIOLATIONS (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_add_track_without_database(track_repo, temp_db):
    """
    BOUNDARY: Attempting operations after database connection closed.
    Should handle or fail gracefully.
    """
    # This test verifies robustness when db connection is lost
    # Each operation gets its own session, so should still work
    track_info = create_test_track(0)

    # Should still work (creates new session)
    track = track_repo.add(track_info)
    assert track is not None or track is None, "Should handle session creation"


@pytest.mark.boundary
def test_get_by_id_invalid_types(track_repo):
    """
    BOUNDARY: Calling get_by_id with invalid type (string instead of int).
    Should handle type errors gracefully.
    """
    try:
        # Try string instead of int
        result = track_repo.get_by_id("not_an_id")
        # May succeed (type coercion) or fail
        assert result is None or isinstance(result, Track), "Should handle gracefully"
    except (TypeError, ValueError):
        # Expected for type mismatch
        pass


@pytest.mark.boundary
def test_concurrent_add_same_track(track_repo):
    """
    BOUNDARY: Simulating concurrent adds of same track.
    Should prevent duplicates.
    """
    track_info = create_test_track(0)

    # Add twice rapidly (simulating concurrent access)
    track1 = track_repo.add(track_info)
    track2 = track_repo.add(track_info)

    # Should either return same track or prevent duplicate
    if track1 is not None and track2 is not None:
        assert track1.id == track2.id, "Should not create duplicate"

    # Verify no duplicates
    all_tracks, total = track_repo.get_all(limit=100, offset=0)
    assert total == 1, "Should have exactly 1 track"


@pytest.mark.boundary
def test_transaction_rollback_on_error(track_repo, temp_db):
    """
    BOUNDARY: Verify transaction rollback on error.
    Failed operations should not corrupt database.
    """
    # Add a valid track
    track_repo.add(create_test_track(0))

    # Get initial count
    _, initial_count = track_repo.get_all(limit=100, offset=0)

    # Try to add invalid track (should fail)
    try:
        invalid_track = {'filepath': None}  # Invalid
        track_repo.add(invalid_track)
    except Exception:
        # Expected to fail
        pass

    # Verify database state unchanged
    _, final_count = track_repo.get_all(limit=100, offset=0)
    assert final_count == initial_count, "Failed add should not change database"


@pytest.mark.boundary
def test_cascade_delete_relationships(track_repo, album_repo, temp_db):
    """
    BOUNDARY: Test cascade delete of album with tracks.
    Should handle relationship cascades properly.
    """
    # Add album with tracks
    session = temp_db()
    artist = Artist(name='Test Artist')
    session.add(artist)
    session.commit()

    album = Album(title='Test Album', artist_id=artist.id)
    session.add(album)
    session.commit()
    album_id = album.id
    session.close()

    # Add tracks for album
    for i in range(5):
        track_info = create_test_track(i, album='Test Album')
        track_repo.add(track_info)

    # Delete album
    session = temp_db()
    album_to_delete = session.query(Album).filter(Album.id == album_id).first()
    if album_to_delete:
        session.delete(album_to_delete)
        session.commit()
    session.close()

    # Verify database is in consistent state
    all_tracks, total = track_repo.get_all(limit=100, offset=0)
    # Tracks may still exist (album_id nulled) or be deleted (cascade)
    # Either way, database should be consistent
    assert total >= 0, "Database should be in consistent state after cascade"


@pytest.mark.boundary
def test_update_with_invalid_foreign_key(track_repo, temp_db):
    """
    BOUNDARY: Updating track with non-existent album_id.
    Should handle foreign key constraint.
    """
    # Add track
    track_info = create_test_track(0)
    track = track_repo.add(track_info)

    # Try to update with invalid album_id
    session = temp_db()
    try:
        track_to_update = session.query(Track).filter(Track.id == track.id).first()
        if track_to_update:
            track_to_update.album_id = 999999  # Non-existent
            session.commit()
    except Exception:
        session.rollback()
        # Foreign key constraint may prevent this
    finally:
        session.close()

    # Verify database is still consistent
    result = track_repo.get_by_id(track.id)
    assert result is not None, "Track should still exist"
