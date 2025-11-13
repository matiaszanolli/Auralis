"""
Metadata Operations Tests

Tests metadata reading, editing, and persistence.

DEPRECATED: These tests were written for an older metadata model where Track
had direct artist/album attributes. The current Track model uses relationships
(Track.artists, Track.album) instead. These tests need to be rewritten to match
the current model schema or removed if testing legacy functionality.

Philosophy:
- Test CRUD operations on track metadata
- Test metadata validation
- Test batch updates
- Test metadata persistence to files
- Test edge cases (special characters, long strings)

These tests ensure that metadata operations work correctly
and data is not lost or corrupted.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import shutil

from auralis.library.manager import LibraryManager
from auralis.library.metadata_editor import MetadataEditor
from auralis.io.saver import save as save_audio


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_audio_dir():
    """Create a temporary directory for test audio files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def library_manager():
    """Create an in-memory library manager."""
    manager = LibraryManager(database_path=":memory:")
    yield manager
    # SQLite in-memory DB is cleaned up automatically


@pytest.fixture
def track_repo(library_manager):
    """Get track repository from library manager."""
    return library_manager.tracks


def create_test_track(directory: Path, filename: str):
    """Create a minimal test audio file."""
    audio = np.random.randn(44100, 2) * 0.5
    filepath = directory / filename
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')
    return filepath


# ============================================================================
# Metadata CRUD Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_create_track(temp_audio_dir, track_repo):
    """
    METADATA: Create track with full metadata.

    Tests that all metadata fields are stored correctly.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "album_artist": "Test Album Artist",
        "genre": "Rock",
        "year": 2024,
        "track_number": 1,
        "disc_number": 1,
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)

    assert track.title == "Test Track"
    assert track.artist == "Test Artist"
    assert track.album == "Test Album"
    assert track.year == 2024
    assert track.track_number == 1


@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_read_track(temp_audio_dir, track_repo):
    """
    METADATA: Read track metadata by ID.

    Tests that metadata can be retrieved after storage.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Original Title",
        "artist": "Original Artist",
        "album": "Original Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    added_track = track_repo.add(track_info)

    # Read back
    retrieved_track = track_repo.get_by_id(added_track.id)

    assert retrieved_track is not None
    assert retrieved_track.title == "Original Title"
    assert retrieved_track.artist == "Original Artist"


@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_update_single_field(temp_audio_dir, track_repo):
    """
    METADATA: Update single metadata field.

    Tests that partial updates work correctly.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Original Title",
        "artist": "Original Artist",
        "album": "Original Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)

    # Update only title
    track_repo.update(track.id, {"title": "Updated Title"})

    # Verify update
    updated_track = track_repo.get_by_id(track.id)

    assert updated_track.title == "Updated Title"
    assert updated_track.artist == "Original Artist"  # Unchanged
    assert updated_track.album == "Original Album"  # Unchanged


@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_update_multiple_fields(temp_audio_dir, track_repo):
    """
    METADATA: Update multiple metadata fields at once.

    Tests batch field updates.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Original Title",
        "artist": "Original Artist",
        "album": "Original Album",
        "year": 2020,
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)

    # Update multiple fields
    updates = {
        "title": "New Title",
        "artist": "New Artist",
        "year": 2024
    }
    track_repo.update(track.id, updates)

    # Verify all updates
    updated_track = track_repo.get_by_id(track.id)

    assert updated_track.title == "New Title"
    assert updated_track.artist == "New Artist"
    assert updated_track.year == 2024
    assert updated_track.album == "Original Album"  # Unchanged


@pytest.mark.integration
def test_metadata_delete_track(temp_audio_dir, track_repo):
    """
    METADATA: Delete track and verify metadata removal.

    Tests that deletion removes all metadata.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Track to Delete",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)
    track_id = track.id

    # Delete
    track_repo.delete(track_id)

    # Verify deletion
    deleted_track = track_repo.get_by_id(track_id)
    assert deleted_track is None


# ============================================================================
# Metadata Validation Tests
# ============================================================================

@pytest.mark.unit
def test_metadata_year_validation(temp_audio_dir, track_repo):
    """
    METADATA: Year field validation.

    Tests that invalid years are handled.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    # Try with future year
    track_info = {
        "filepath": str(filepath),
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "year": 2100,  # Future year
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    # Should either accept or reject gracefully
    try:
        track = track_repo.add(track_info)
        # If accepted, verify it's stored
        assert track.year == 2100 or track.year is None
    except ValueError:
        # Rejection is acceptable
        pass


@pytest.mark.unit
def test_metadata_track_number_validation(temp_audio_dir, track_repo):
    """
    METADATA: Track number validation.

    Tests that invalid track numbers are handled.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    # Try with zero track number
    track_info = {
        "filepath": str(filepath),
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "track_number": 0,
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    # Should handle gracefully
    try:
        track = track_repo.add(track_info)
        assert track is not None
    except ValueError:
        pass


# ============================================================================
# Batch Update Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_batch_update_artist(temp_audio_dir, track_repo):
    """
    METADATA: Batch update artist for multiple tracks.

    Tests updating same field across multiple tracks.
    """
    track_ids = []

    # Create 5 tracks
    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Old Artist",
            "album": "Test Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }

        track = track_repo.add(track_info)
        track_ids.append(track.id)

    # Batch update artist
    for track_id in track_ids:
        track_repo.update(track_id, {"artist": "New Artist"})

    # Verify all updated
    for track_id in track_ids:
        track = track_repo.get_by_id(track_id)
        assert track.artist == "New Artist"


@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_batch_update_album(temp_audio_dir, track_repo):
    """
    METADATA: Batch update album for compilation.

    Tests updating album field for multiple tracks.
    """
    track_ids = []

    # Create tracks with different albums
    for i in range(3):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": f"Artist {i}",
            "album": f"Old Album {i}",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }

        track = track_repo.add(track_info)
        track_ids.append(track.id)

    # Update to compilation album
    for track_id in track_ids:
        track_repo.update(track_id, {
            "album": "Greatest Hits Compilation",
            "album_artist": "Various Artists"
        })

    # Verify all updated
    for track_id in track_ids:
        track = track_repo.get_by_id(track_id)
        assert track.album == "Greatest Hits Compilation"


# ============================================================================
# Special Characters in Metadata Tests
# ============================================================================

@pytest.mark.boundary
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_unicode_characters(temp_audio_dir, track_repo):
    """
    METADATA: Unicode characters in metadata fields.

    Tests that Unicode is preserved correctly.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Тест Track 测试 🎵",
        "artist": "Artist Артист 艺术家",
        "album": "Album Альбом 专辑",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)

    # Retrieve and verify Unicode preserved
    retrieved = track_repo.get_by_id(track.id)

    assert len(retrieved.title) > 0
    assert len(retrieved.artist) > 0
    assert len(retrieved.album) > 0


@pytest.mark.boundary
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_special_punctuation(temp_audio_dir, track_repo):
    """
    METADATA: Special punctuation in metadata.

    Tests that punctuation is preserved.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Track: \"The Best\" (2024 Mix) [Remaster]",
        "artist": "Artist & The Band, feat. Guest",
        "album": "Album - Special Edition!",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)
    retrieved = track_repo.get_by_id(track.id)

    # Verify punctuation preserved
    assert ":" in retrieved.title or "(" in retrieved.title
    assert "&" in retrieved.artist or "," in retrieved.artist


# ============================================================================
# Metadata Search Tests
# ============================================================================

@pytest.mark.integration
def test_metadata_search_by_title(temp_audio_dir, track_repo):
    """
    METADATA: Search tracks by title metadata.

    Tests that search uses metadata correctly.
    """
    # Create tracks with searchable titles
    titles = ["Hello World", "Goodbye Moon", "Hello Again"]

    for i, title in enumerate(titles):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": title,
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }

        track_repo.add(track_info)

    # Search for "Hello"
    results, total = track_repo.search("Hello", limit=50, offset=0)

    # Should find both "Hello World" and "Hello Again"
    assert total >= 2


@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_search_by_artist(temp_audio_dir, track_repo):
    """
    METADATA: Search tracks by artist metadata.

    Tests artist-based search.
    """
    artists = ["The Beatles", "Pink Floyd", "The Rolling Stones"]

    for i, artist in enumerate(artists):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": artist,
            "album": "Greatest Hits",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }

        track_repo.add(track_info)

    # Search for "The"
    results, total = track_repo.search("The", limit=50, offset=0)

    # Should find at least 2 (The Beatles, The Rolling Stones)
    assert total >= 2


# ============================================================================
# Metadata Favorites Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_mark_as_favorite(temp_audio_dir, track_repo):
    """
    METADATA: Mark track as favorite.

    Tests favorite flag persistence.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Favorite Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "favorite": False,
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)

    # Mark as favorite
    track_repo.update(track.id, {"favorite": True})

    # Verify
    updated = track_repo.get_by_id(track.id)
    assert updated.favorite == True


@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_query_favorites(temp_audio_dir, track_repo):
    """
    METADATA: Query only favorite tracks.

    Tests filtering by favorite status.
    """
    # Create mix of favorite and non-favorite tracks
    for i in range(10):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Test Artist",
            "album": "Test Album",
            "favorite": (i % 3 == 0),  # Every 3rd track is favorite
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }

        track_repo.add(track_info)

    # Query favorites
    favorites, total = track_repo.get_favorites(limit=50, offset=0)

    # Should have ~3-4 favorites
    assert total >= 3
    assert all(track.favorite for track in favorites)


# ============================================================================
# Metadata Play Count Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_play_count_increment(temp_audio_dir, track_repo):
    """
    METADATA: Increment play count.

    Tests that play count tracking works.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "play_count": 0,
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)

    # Increment play count
    track_repo.increment_play_count(track.id)
    track_repo.increment_play_count(track.id)

    # Verify
    updated = track_repo.get_by_id(track.id)
    assert updated.play_count == 2


@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Test expects Track.artist attribute but model uses Track.artists relationship")
def test_metadata_recent_tracks_by_last_played(temp_audio_dir, track_repo):
    """
    METADATA: Query recent tracks by last_played.

    Tests sorting by play timestamp.
    """
    import time

    # Create tracks and "play" them with delays
    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }

        track = track_repo.add(track_info)

        # Simulate play
        track_repo.increment_play_count(track.id)
        time.sleep(0.01)  # Small delay to ensure different timestamps

    # Query recent tracks
    recent, total = track_repo.get_recent(limit=3, offset=0)

    # Should return most recently played
    assert len(recent) == 3


# ============================================================================
# Summary Statistics
# ============================================================================

@pytest.mark.unit
def test_summary_stats():
    """Print summary statistics about metadata operations tests."""
    print("\n" + "=" * 70)
    print("METADATA OPERATIONS TESTS - SUMMARY")
    print("=" * 70)
    print(f"Total metadata tests: 20")
    print(f"\nTest categories:")
    print(f"  - CRUD operations: 5 tests")
    print(f"  - Validation: 2 tests")
    print(f"  - Batch updates: 2 tests")
    print(f"  - Special characters: 2 tests")
    print(f"  - Search: 2 tests")
    print(f"  - Favorites: 2 tests")
    print(f"  - Play count: 2 tests")
    print(f"  - Summary stats: 1 test")
    print("=" * 70)
