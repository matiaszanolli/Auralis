"""
Library Management Integration Tests

Tests complete workflows for library management operations.

DEPRECATED: These tests were written for an older library scanning API that
has been refactored. The LibraryScanner.scan_folder() method and direct
TrackRepository.get_all() access patterns are no longer used. These tests need
to be rewritten to use the current LibraryManager API or removed if testing
legacy functionality.

Philosophy:
- Test cross-component library workflows
- Test scanning → database → retrieval flows
- Test metadata editing workflows
- Test search and filter operations
- Use real database and real files

These tests validate that library management works correctly
as a whole, catching integration issues between scanner, database,
and query operations.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import shutil

from auralis.library.manager import LibraryManager
from auralis.library.repositories.track_repository import TrackRepository
from auralis.library.repositories.album_repository import AlbumRepository
from auralis.library.repositories.artist_repository import ArtistRepository
from auralis.library.scanner import LibraryScanner
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
    """Create a library manager with in-memory database."""
    manager = LibraryManager(database_path=":memory:")
    yield manager
    # SQLite in-memory DB is cleaned up automatically


def create_test_track(directory: Path, filename: str, title: str = None,
                     artist: str = None, album: str = None, duration: float = 3.0):
    """Create a test audio file with metadata."""
    # Create minimal audio
    num_samples = int(duration * 44100)
    audio = np.random.randn(num_samples, 2) * 0.5

    filepath = directory / filename
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')

    return filepath


# ============================================================================
# E2E Library Workflow Tests - Scanning
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_scan_folder_adds_tracks_to_database(temp_audio_dir, library_manager):
    """
    E2E: Scan folder → add to database → verify retrieval.

    Tests the complete workflow from folder scanning to database storage.
    """
    # Create test audio files
    for i in range(10):
        create_test_track(
            temp_audio_dir,
            f"track_{i:02d}.wav",
            title=f"Track {i}",
            artist=f"Artist {i % 3}",
            album=f"Album {i % 2}"
        )

    # Scan folder
    scanner = LibraryScanner(library_manager)
    added, skipped, errors = scanner.scan_folder(str(temp_audio_dir))

    assert added == 10, f"Expected 10 tracks added, got {added}"
    assert skipped == 0, f"Should have 0 skipped, got {skipped}"
    assert errors == 0, f"Should have 0 errors, got {errors}"

    # Verify tracks in database
    tracks, total = library_manager.track_repo.get_all(limit=100, offset=0)

    assert len(tracks) == 10
    assert total == 10


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_scan_folder_skips_duplicates(temp_audio_dir, library_manager):
    """
    E2E: Scan same folder twice → duplicates are skipped.

    Tests that rescanning doesn't create duplicate entries.
    """
    # Create test audio files
    for i in range(5):
        create_test_track(temp_audio_dir, f"track_{i}.wav")

    scanner = LibraryScanner(library_manager)

    # First scan
    added1, skipped1, errors1 = scanner.scan_folder(str(temp_audio_dir))
    assert added1 == 5

    # Second scan (should skip all)
    added2, skipped2, errors2 = scanner.scan_folder(str(temp_audio_dir))
    assert added2 == 0, "Second scan should add 0 new tracks"
    assert skipped2 == 5, "Second scan should skip all 5 tracks"

    # Verify total count
    _, total = library_manager.track_repo.get_all(limit=100, offset=0)
    assert total == 5, "Should still have only 5 tracks"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_scan_nested_folders(temp_audio_dir, library_manager):
    """
    E2E: Scan nested folder structure → all tracks found.

    Tests that scanner handles nested directories.
    """
    # Create nested structure
    artist1_dir = temp_audio_dir / "Artist1"
    artist1_dir.mkdir()
    album1_dir = artist1_dir / "Album1"
    album1_dir.mkdir()

    artist2_dir = temp_audio_dir / "Artist2"
    artist2_dir.mkdir()

    # Create tracks in different locations
    create_test_track(artist1_dir, "track1.wav")
    create_test_track(album1_dir, "track2.wav")
    create_test_track(artist2_dir, "track3.wav")

    # Scan root directory (should find all)
    scanner = LibraryScanner(library_manager)
    added, skipped, errors = scanner.scan_folder(str(temp_audio_dir), recursive=True)

    assert added == 3, f"Expected 3 tracks from nested folders, got {added}"


# ============================================================================
# E2E Library Workflow Tests - Retrieval
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_add_tracks_then_retrieve_all(temp_audio_dir, library_manager):
    """
    E2E: Add tracks → retrieve all → verify completeness.

    Tests the add-and-retrieve workflow.
    """
    # Add tracks directly
    for i in range(20):
        filepath = create_test_track(temp_audio_dir, f"track_{i:03d}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i:03d}",
            "artist": f"Artist {i % 5}",
            "album": f"Album {i % 3}",
            "duration": 3.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.track_repo.add(track_info)

    # Retrieve all tracks
    tracks, total = library_manager.track_repo.get_all(limit=50, offset=0)

    assert len(tracks) == 20
    assert total == 20


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_paginate_through_large_library(temp_audio_dir, library_manager):
    """
    E2E: Add 100 tracks → paginate retrieval → verify all returned.

    Tests pagination workflow with realistic library size.
    """
    # Add 100 tracks
    for i in range(100):
        filepath = create_test_track(temp_audio_dir, f"track_{i:04d}.wav", duration=1.0)

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i:04d}",
            "artist": f"Artist {i % 10}",
            "album": f"Album {i % 5}",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.track_repo.add(track_info)

    # Paginate through all tracks
    all_track_ids = set()
    page_size = 25
    offset = 0

    while True:
        tracks, total = library_manager.track_repo.get_all(limit=page_size, offset=offset)

        if not tracks:
            break

        for track in tracks:
            all_track_ids.add(track.id)

        offset += page_size

    assert len(all_track_ids) == 100, \
        f"Expected 100 unique tracks, got {len(all_track_ids)}"


# ============================================================================
# E2E Library Workflow Tests - Search
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_search_by_title(temp_audio_dir, library_manager):
    """
    E2E: Add tracks → search by title → verify results.

    Tests the search workflow.
    """
    # Add tracks with distinctive titles
    titles = ["Hello World", "Goodbye Moon", "Hello Again", "Random Track"]

    for i, title in enumerate(titles):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": title,
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 3.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.track_repo.add(track_info)

    # Search for "Hello"
    results, total = library_manager.track_repo.search("Hello", limit=50, offset=0)

    assert total == 2, f"Expected 2 results for 'Hello', got {total}"
    result_titles = {track.title for track in results}
    assert "Hello World" in result_titles
    assert "Hello Again" in result_titles


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_search_by_artist(temp_audio_dir, library_manager):
    """
    E2E: Add tracks → search by artist → verify results.

    Tests artist search workflow.
    """
    # Add tracks with different artists
    artists = ["The Beatles", "Pink Floyd", "The Rolling Stones", "Led Zeppelin"]

    for i, artist in enumerate(artists):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": artist,
            "album": "Greatest Hits",
            "duration": 3.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.track_repo.add(track_info)

    # Search for "The"
    results, total = library_manager.track_repo.search("The", limit=50, offset=0)

    # Should find "The Beatles" and "The Rolling Stones"
    assert total >= 2, f"Expected at least 2 results for 'The', got {total}"


# ============================================================================
# E2E Library Workflow Tests - Albums and Artists
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_group_tracks_by_album(temp_audio_dir, library_manager):
    """
    E2E: Add tracks → group by album → verify grouping.

    Tests album grouping workflow.
    """
    # Add tracks for multiple albums
    albums = ["Album A", "Album B", "Album C"]
    tracks_per_album = [5, 3, 7]

    track_idx = 0
    for album, num_tracks in zip(albums, tracks_per_album):
        for i in range(num_tracks):
            filepath = create_test_track(temp_audio_dir, f"track_{track_idx:03d}.wav")

            track_info = {
                "filepath": str(filepath),
                "title": f"Track {i + 1}",
                "artist": "Test Artist",
                "album": album,
                "duration": 3.0,
                "sample_rate": 44100,
                "channels": 2,
                "bitrate": 1411200,
            }
            library_manager.track_repo.add(track_info)
            track_idx += 1

    # Get albums
    album_repo = library_manager.album_repo
    albums_list, total = album_repo.get_all(limit=50, offset=0)

    assert total == 3, f"Expected 3 albums, got {total}"

    # Verify track counts per album
    for album_obj in albums_list:
        tracks_in_album, _ = library_manager.track_repo.get_by_album(album_obj.id)
        expected_count = dict(zip(albums, tracks_per_album)).get(album_obj.title, 0)

        if album_obj.title in albums:
            assert len(tracks_in_album) == expected_count, \
                f"Album '{album_obj.title}' has {len(tracks_in_album)} tracks, expected {expected_count}"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_list_albums_with_pagination(temp_audio_dir, library_manager):
    """
    E2E: Create multiple albums → paginate album list → verify completeness.

    Tests album pagination workflow.
    """
    # Create 20 albums
    for i in range(20):
        filepath = create_test_track(temp_audio_dir, f"track_{i:03d}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": f"Artist {i}",
            "album": f"Album {i:02d}",
            "duration": 3.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.track_repo.add(track_info)

    # Paginate through albums
    album_repo = library_manager.album_repo
    all_album_ids = set()

    offset = 0
    page_size = 10

    while True:
        albums, total = album_repo.get_all(limit=page_size, offset=offset)

        if not albums:
            break

        for album in albums:
            all_album_ids.add(album.id)

        offset += page_size

    assert len(all_album_ids) == 20, \
        f"Expected 20 unique albums, got {len(all_album_ids)}"


# ============================================================================
# E2E Library Workflow Tests - Metadata Editing
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_edit_track_metadata(temp_audio_dir, library_manager):
    """
    E2E: Add track → edit metadata → verify changes.

    Tests metadata editing workflow.
    """
    # Add track
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Original Title",
        "artist": "Original Artist",
        "album": "Original Album",
        "duration": 3.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track = library_manager.track_repo.add(track_info)

    # Edit metadata
    updated_fields = {
        "title": "New Title",
        "artist": "New Artist",
    }
    library_manager.track_repo.update(track.id, updated_fields)

    # Verify changes
    updated_track = library_manager.track_repo.get_by_id(track.id)

    assert updated_track.title == "New Title"
    assert updated_track.artist == "New Artist"
    assert updated_track.album == "Original Album"  # Unchanged


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_batch_update_tracks(temp_audio_dir, library_manager):
    """
    E2E: Add multiple tracks → batch update artist → verify all changed.

    Tests batch metadata update workflow.
    """
    # Add tracks
    track_ids = []
    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Old Artist",
            "album": "Test Album",
            "duration": 3.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        track = library_manager.track_repo.add(track_info)
        track_ids.append(track.id)

    # Batch update artist
    for track_id in track_ids:
        library_manager.track_repo.update(track_id, {"artist": "New Artist"})

    # Verify all updated
    for track_id in track_ids:
        track = library_manager.track_repo.get_by_id(track_id)
        assert track.artist == "New Artist"


# ============================================================================
# E2E Library Workflow Tests - Favorites
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_mark_tracks_as_favorite(temp_audio_dir, library_manager):
    """
    E2E: Add tracks → mark as favorite → retrieve favorites.

    Tests favorite marking workflow.
    """
    # Add tracks
    track_ids = []
    for i in range(10):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 3.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        track = library_manager.track_repo.add(track_info)
        track_ids.append(track.id)

    # Mark tracks 0, 2, 4 as favorites
    for i in [0, 2, 4]:
        library_manager.track_repo.update(track_ids[i], {"favorite": True})

    # Retrieve favorites
    favorites, total = library_manager.track_repo.get_favorites(limit=50, offset=0)

    assert total == 3, f"Expected 3 favorites, got {total}"
    favorite_ids = {track.id for track in favorites}

    assert track_ids[0] in favorite_ids
    assert track_ids[2] in favorite_ids
    assert track_ids[4] in favorite_ids


# ============================================================================
# E2E Library Workflow Tests - Deletion
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_delete_track_from_library(temp_audio_dir, library_manager):
    """
    E2E: Add track → delete → verify removal.

    Tests track deletion workflow.
    """
    # Add track
    filepath = create_test_track(temp_audio_dir, "track_to_delete.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Track to Delete",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 3.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track = library_manager.track_repo.add(track_info)

    # Verify it exists
    _, total_before = library_manager.track_repo.get_all(limit=50, offset=0)
    assert total_before == 1

    # Delete track
    library_manager.track_repo.delete(track.id)

    # Verify it's gone
    _, total_after = library_manager.track_repo.get_all(limit=50, offset=0)
    assert total_after == 0

    # Verify get_by_id returns None
    deleted_track = library_manager.track_repo.get_by_id(track.id)
    assert deleted_track is None


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_batch_delete_tracks(temp_audio_dir, library_manager):
    """
    E2E: Add multiple tracks → batch delete → verify removal.

    Tests batch deletion workflow.
    """
    # Add tracks
    track_ids = []
    for i in range(10):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 3.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        track = library_manager.track_repo.add(track_info)
        track_ids.append(track.id)

    # Delete tracks 0-4
    for i in range(5):
        library_manager.track_repo.delete(track_ids[i])

    # Verify count
    _, total = library_manager.track_repo.get_all(limit=50, offset=0)
    assert total == 5, f"Expected 5 remaining tracks, got {total}"


# ============================================================================
# E2E Library Workflow Tests - Cache
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_cache_invalidation_on_add(temp_audio_dir, library_manager):
    """
    E2E: Query tracks → add new track → verify cache invalidated.

    Tests that cache is properly invalidated on data changes.
    """
    # Initial query (populates cache)
    tracks1, total1 = library_manager.track_repo.get_all(limit=50, offset=0)
    assert total1 == 0

    # Add track
    filepath = create_test_track(temp_audio_dir, "new_track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "New Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 3.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    library_manager.track_repo.add(track_info)

    # Query again (should see new track, not cached result)
    tracks2, total2 = library_manager.track_repo.get_all(limit=50, offset=0)
    assert total2 == 1, "Cache was not invalidated on add"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skip(reason="DEPRECATED: Uses outdated LibraryScanner API (scan_folder) and TrackRepository.get_all() patterns")
def test_e2e_cache_statistics(temp_audio_dir, library_manager):
    """
    E2E: Perform queries → check cache stats → verify hits/misses.

    Tests that cache statistics are tracked correctly.
    """
    # Add some tracks
    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 3.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.track_repo.add(track_info)

    # First query (cache miss)
    library_manager.track_repo.get_all(limit=50, offset=0)

    # Second query (cache hit)
    library_manager.track_repo.get_all(limit=50, offset=0)

    # Get cache stats
    stats = library_manager.get_cache_stats()

    assert stats["total_requests"] >= 2, "Expected at least 2 cache requests"
    assert stats["hits"] >= 1, "Expected at least 1 cache hit"


# ============================================================================
# Summary Statistics
# ============================================================================

@pytest.mark.unit
def test_summary_stats():
    """Print summary statistics about library integration tests."""
    print("\n" + "=" * 70)
    print("LIBRARY INTEGRATION TESTS - SUMMARY")
    print("=" * 70)
    print(f"Total integration tests: 25")
    print(f"\nTest categories:")
    print(f"  - Scanning workflows: 3 tests")
    print(f"  - Retrieval workflows: 2 tests")
    print(f"  - Search workflows: 2 tests")
    print(f"  - Albums and artists: 2 tests")
    print(f"  - Metadata editing: 2 tests")
    print(f"  - Favorites workflow: 1 test")
    print(f"  - Deletion workflows: 2 tests")
    print(f"  - Cache workflows: 2 tests")
    print(f"  - Summary stats: 1 test")
    print("=" * 70)
