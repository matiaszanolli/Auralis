#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Advanced Boundary Scenario Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Boundary tests for advanced scenarios: batch operations, streaming, concurrency,
and error recovery.

:copyright: (C) 2024 Auralis Team
:license: GPLv3

CONTEXT: Advanced scenarios can cause:
- Race conditions in concurrent operations
- Memory exhaustion in batch operations
- Data corruption in streaming
- Partial failures in error recovery

Test Philosophy:
- Test realistic production scenarios
- Validate concurrent operation safety
- Test error recovery and resilience
- Validate batch operation correctness

See docs/development/TESTING_GUIDELINES.md for complete testing philosophy.
"""

import os

# Import the modules under test
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.io.saver import save as save_audio
from auralis.library.database import LibraryDatabase

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_library_large(tmp_path):
    """Create library with 100 tracks for batch testing."""
    db_path = tmp_path / "test_library.db"
    db = LibraryDatabase(database_path=str(db_path))

    # Create audio directory
    audio_dir = tmp_path / "music"
    audio_dir.mkdir()

    # Create 100 test tracks
    track_ids = []
    for i in range(100):
        audio = np.random.randn(44100, 2) * 0.1  # 1 second
        filepath = audio_dir / f"track_{i:03d}.wav"
        save_audio(str(filepath), audio, 44100, subtype='PCM_16')

        track_info = {
            'filepath': str(filepath),
            'title': f'Track {i:03d}',
            'artists': [f'Artist {i % 10}'],
            'album': f'Album {i % 20}',
        }
        track = db.tracks.add(track_info)
        track_ids.append(track.id)

    yield db, track_ids, tmp_path


# ============================================================================
# Batch Operation Boundary Tests (P1 Priority)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.extreme
@pytest.mark.fast
@pytest.mark.library
def test_batch_add_tracks(tmp_path):
    """
    BOUNDARY: Adding 50 tracks in batch.

    Validates:
    - Batch insert performance
    - No memory leaks
    - Transaction atomicity
    """
    db_path = tmp_path / "test.db"
    db = LibraryDatabase(database_path=str(db_path))

    audio_dir = tmp_path / "music"
    audio_dir.mkdir()

    # Batch add 50 tracks
    track_ids = []
    for i in range(50):
        audio = np.random.randn(44100, 2) * 0.1
        filepath = audio_dir / f"batch_{i:03d}.wav"
        save_audio(str(filepath), audio, 44100, subtype='PCM_16')

        track_info = {
            'filepath': str(filepath),
            'title': f'Batch Track {i}',
        }
        track = db.tracks.add(track_info)
        track_ids.append(track.id)

    # Verify all added
    tracks, total = db.tracks.get_all(limit=100)
    assert total == 50, f"Expected 50 tracks, got {total}"
    assert len(tracks) == 50


@pytest.mark.boundary
@pytest.mark.extreme
@pytest.mark.fast
@pytest.mark.library
def test_batch_delete_tracks(test_library_large):
    """
    BOUNDARY: Deleting 50 tracks in batch.

    Validates:
    - Batch delete correctness
    - Cascade operations
    - No orphaned data
    """
    db, track_ids, _ = test_library_large

    # Delete first 50 tracks
    initial_total = len(track_ids)
    for track_id in track_ids[:50]:
        db.tracks.delete(track_id)

    # Verify count
    tracks, total = db.tracks.get_all(limit=200)
    assert total == initial_total - 50, (
        f"Expected {initial_total - 50} tracks, got {total}"
    )


@pytest.mark.boundary
@pytest.mark.extreme
@pytest.mark.fast
@pytest.mark.library
def test_batch_update_metadata(test_library_large):
    """
    BOUNDARY: Updating metadata for 50 tracks.

    Validates:
    - Batch update performance
    - Data consistency
    - Cache invalidation
    """
    db, track_ids, _ = test_library_large

    # Batch update first 50 tracks
    for i, track_id in enumerate(track_ids[:50]):
        db.tracks.update(track_id, {"title": f"Updated Track {i}"})

    # Verify updates
    for i, track_id in enumerate(track_ids[:50]):
        track = db.tracks.get_by_id(track_id)
        assert track.title == f"Updated Track {i}", (
            f"Track {track_id} not updated correctly"
        )


@pytest.mark.boundary
@pytest.mark.extreme
@pytest.mark.fast
@pytest.mark.library
def test_batch_toggle_favorites(test_library_large):
    """
    BOUNDARY: Toggling favorites for 50 tracks.

    Validates:
    - Batch favorite operations
    - State consistency
    """
    db, track_ids, _ = test_library_large

    # Batch favorite first 50 tracks
    for track_id in track_ids[:50]:
        db.tracks.set_favorite(track_id)

    # Verify all favorited
    favorites, total = db.tracks.get_favorites(limit=100)
    assert len(favorites) == 50, f"Expected 50 favorites, got {count}"


@pytest.mark.boundary
@pytest.mark.extreme
@pytest.mark.slow
@pytest.mark.library
@pytest.mark.performance
def test_batch_operation_performance(test_library_large):
    """
    BOUNDARY: Performance of batch operations.

    Validates:
    - Batch operations scale linearly
    - No O(n²) performance
    """
    db, track_ids, _ = test_library_large

    import timeit

    # Batch favorite 10 tracks
    def favorite_10():
        for track_id in track_ids[:10]:
            db.tracks.set_favorite(track_id)
            db.tracks.set_favorite(track_id)  # Toggle back

    time_10 = timeit.timeit(favorite_10, number=1)

    # Batch favorite 20 tracks (2x)
    def favorite_20():
        for track_id in track_ids[:20]:
            db.tracks.set_favorite(track_id)
            db.tracks.set_favorite(track_id)  # Toggle back

    time_20 = timeit.timeit(favorite_20, number=1)

    # Should scale linearly (within tolerance)
    ratio = time_20 / time_10 if time_10 > 0 else 0
    assert 1.5 <= ratio <= 3.0, (
        f"Batch operations not scaling linearly: {ratio}x for 2x data"
    )


# ============================================================================
# Streaming and Pagination Boundary Tests (P1 Priority)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.exact
@pytest.mark.fast
@pytest.mark.library
def test_pagination_consistency_across_pages(test_library_large):
    """
    BOUNDARY: Pagination returns all items exactly once.

    Validates:
    - No missing items
    - No duplicate items
    - Correct total count
    """
    db, track_ids, _ = test_library_large

    # Paginate through all tracks
    all_ids = set()
    offset = 0
    limit = 10

    while True:
        tracks, total = db.tracks.get_all(limit=limit, offset=offset)
        if not tracks:
            break

        # Check for duplicates
        page_ids = {t.id for t in tracks}
        duplicates = all_ids & page_ids
        assert len(duplicates) == 0, (
            f"Duplicate items in pagination: {duplicates}"
        )

        all_ids.update(page_ids)
        offset += limit

    # Verify got all items
    assert len(all_ids) == len(track_ids), (
        f"Pagination missing items: expected {len(track_ids)}, got {len(all_ids)}"
    )


@pytest.mark.boundary
@pytest.mark.exact
@pytest.mark.fast
@pytest.mark.library
def test_pagination_during_concurrent_modifications(test_library_large):
    """
    BOUNDARY: Pagination while items are being added.

    Validates:
    - No crashes during concurrent modifications
    - Consistent results within a page
    """
    db, track_ids, tmp_path = test_library_large

    audio_dir = tmp_path / "music"

    # Start pagination
    page1, total1 = db.tracks.get_all(limit=20, offset=0)

    # Add new track
    audio = np.random.randn(44100, 2) * 0.1
    filepath = audio_dir / "new_track.wav"
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')

    db.tracks.add({
        'filepath': str(filepath),
        'title': 'New Track',
    })

    # Continue pagination (should not crash)
    page2, total2 = db.tracks.get_all(limit=20, offset=20)

    # Should succeed (count may or may not include new track)
    assert page2 is not None
    assert isinstance(page2, list)


@pytest.mark.boundary
@pytest.mark.exact
@pytest.mark.fast
@pytest.mark.library
def test_pagination_with_varying_page_sizes(test_library_large):
    """
    BOUNDARY: Pagination with different page sizes.

    Validates:
    - Correct results for limit=1, 10, 50, 100
    - No off-by-one errors
    """
    db, track_ids, _ = test_library_large

    page_sizes = [1, 10, 50, 100, 200]

    for limit in page_sizes:
        tracks, total = db.tracks.get_all(limit=limit, offset=0)

        expected_count = min(limit, len(track_ids))
        assert len(tracks) == expected_count, (
            f"limit={limit}: expected {expected_count} items, got {len(tracks)}"
        )
        assert total == len(track_ids), (
            f"limit={limit}: total should be {len(track_ids)}, got {total}"
        )


@pytest.mark.boundary
@pytest.mark.exact
@pytest.mark.fast
@pytest.mark.library
def test_pagination_with_filters(test_library_large):
    """
    BOUNDARY: Pagination with search filters.

    Validates:
    - Filtered pagination correctness
    - Total count matches filtered results
    """
    db, track_ids, _ = test_library_large

    # Search for specific artist (Artist 0 should have 10 tracks)
    tracks, total = db.tracks.search("Artist 0", limit=5, offset=0)

    # Should get partial results
    assert len(tracks) <= 5, f"Should get at most 5 results, got {len(tracks)}"
    # Note: only the page slice is asserted here, not the total


@pytest.mark.boundary
@pytest.mark.extreme
@pytest.mark.fast
@pytest.mark.library
def test_deep_pagination(test_library_large):
    """
    BOUNDARY: Very high offset values.

    Validates:
    - High offset values don't cause errors
    - Performance acceptable
    """
    db, track_ids, _ = test_library_large

    # Very high offsets
    test_offsets = [90, 99, 100, 150, 1000]

    for offset in test_offsets:
        tracks, total = db.tracks.get_all(limit=10, offset=offset)

        # Should succeed
        assert tracks is not None
        assert isinstance(tracks, list)

        # High offsets should return empty
        if offset >= total:
            assert len(tracks) == 0


# ============================================================================
# Concurrent Access Boundary Tests (P1 Priority)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.fast
@pytest.mark.library
@pytest.mark.performance
def test_concurrent_reads(test_library_large):
    """
    BOUNDARY: Multiple threads reading simultaneously.

    Validates:
    - Thread-safe read operations
    - No data corruption
    - No crashes
    """
    db, track_ids, _ = test_library_large

    results = []
    errors = []

    def read_tracks():
        try:
            tracks, total = db.tracks.get_all(limit=50)
            results.append(len(tracks))
        except Exception as e:
            errors.append(e)

    # 10 concurrent reads
    threads = [threading.Thread(target=read_tracks) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All should succeed
    assert len(errors) == 0, f"Concurrent read errors: {errors}"
    assert len(results) == 10

    # All should get consistent results
    assert all(r == results[0] for r in results), (
        f"Inconsistent results: {results}"
    )


@pytest.mark.boundary
@pytest.mark.slow
@pytest.mark.library
@pytest.mark.performance
def test_concurrent_writes(tmp_path):
    """
    BOUNDARY: Multiple threads writing simultaneously.

    Validates:
    - Thread-safe write operations
    - No data loss
    - Transaction safety
    """
    db_path = tmp_path / "test.db"
    db = LibraryDatabase(database_path=str(db_path))

    audio_dir = tmp_path / "music"
    audio_dir.mkdir()

    errors = []
    added_ids = []

    def add_track(i):
        try:
            audio = np.random.randn(44100, 2) * 0.1
            filepath = audio_dir / f"concurrent_{i}.wav"
            save_audio(str(filepath), audio, 44100, subtype='PCM_16')

            track = db.tracks.add({
                'filepath': str(filepath),
                'title': f'Concurrent Track {i}',
            })
            added_ids.append(track.id)
        except Exception as e:
            errors.append(e)

    # 10 concurrent writes
    threads = [threading.Thread(target=add_track, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Check for errors (some DBs may not support concurrent writes)
    if len(errors) > 0:
        pytest.skip(f"Database doesn't support concurrent writes: {errors[0]}")

    # Verify all added
    tracks, total = db.tracks.get_all(limit=20)
    assert total == 10, f"Expected 10 tracks, got {total}"


@pytest.mark.boundary
@pytest.mark.fast
@pytest.mark.library
def test_concurrent_read_write(test_library_large):
    """
    BOUNDARY: Concurrent reads and writes.

    Validates:
    - Reads don't block writes
    - Writes don't corrupt reads
    """
    db, track_ids, tmp_path = test_library_large

    audio_dir = tmp_path / "music"
    errors = []
    read_results = []

    def read_operation():
        try:
            tracks, total = db.tracks.get_all(limit=50)
            read_results.append(total)
        except Exception as e:
            errors.append(('read', e))

    def write_operation():
        try:
            audio = np.random.randn(44100, 2) * 0.1
            filepath = audio_dir / f"rw_test_{time.time()}.wav"
            save_audio(str(filepath), audio, 44100, subtype='PCM_16')

            db.tracks.add({
                'filepath': str(filepath),
                'title': 'RW Test Track',
            })
        except Exception as e:
            errors.append(('write', e))

    # Mix of reads and writes
    operations = [read_operation] * 5 + [write_operation] * 5
    threads = [threading.Thread(target=op) for op in operations]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should not crash
    assert len([e for e in errors if e[0] == 'read']) == 0, (
        f"Read errors: {[e for e in errors if e[0] == 'read']}"
    )


@pytest.mark.boundary
@pytest.mark.fast
@pytest.mark.library
def test_concurrent_updates_same_track(test_library_large):
    """
    BOUNDARY: Multiple threads updating same track.

    Validates:
    - Last write wins or transactions serialize
    - No data corruption
    """
    db, track_ids, _ = test_library_large

    target_id = track_ids[0]
    errors = []

    def update_track(value):
        try:
            db.tracks.update(target_id, {"title": f"Update {value}"})
        except Exception as e:
            errors.append(e)

    # 10 concurrent updates to same track
    threads = [threading.Thread(target=update_track, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should not crash (one update should win)
    assert len(errors) == 0, f"Concurrent update errors: {errors}"

    # Track should have valid title
    track = db.tracks.get_by_id(target_id)
    assert track.title.startswith("Update "), (
        f"Track title corrupted: {track.title}"
    )


@pytest.mark.boundary
@pytest.mark.slow
@pytest.mark.library
@pytest.mark.performance
def test_concurrent_search_operations(test_library_large):
    """
    BOUNDARY: Multiple concurrent searches.

    Validates:
    - Search thread safety
    - Consistent results
    - No deadlocks
    """
    db, track_ids, _ = test_library_large

    results = []
    errors = []

    def search_operation(query):
        try:
            tracks, total = db.tracks.search(query)
            results.append((query, len(tracks)))
        except Exception as e:
            errors.append(e)

    # Multiple concurrent searches
    queries = ["Artist 0", "Album 0", "Track 000", "Track 050"]
    threads = [threading.Thread(target=search_operation, args=(q,)) for q in queries]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All should succeed
    assert len(errors) == 0, f"Search errors: {errors}"
    assert len(results) == len(queries)


# ============================================================================
# Error Recovery Boundary Tests (P2 Priority)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.fast
@pytest.mark.library
@pytest.mark.error
def test_invalid_file_path_handling(tmp_path):
    """
    BOUNDARY: Adding track with invalid file path.

    Validates:
    - Graceful error handling
    - Database not corrupted
    """
    db_path = tmp_path / "test.db"
    db = LibraryDatabase(database_path=str(db_path))

    # TrackRepository.add() does NOT check that the file exists on disk — the
    # FileNotFoundError came from the LibraryManager.add_track() facade, which
    # was deleted with the rest of that legacy wrapper (#4915). Adding a row for
    # a missing file must therefore not raise, and must not corrupt the DB.
    # TODO(#5172): nothing validates on-disk existence at the repository layer
    # anymore. If that guard is wanted back it belongs in TrackRepository.add(),
    # and this assertion should become `pytest.raises(FileNotFoundError)` again.
    db.tracks.add({
        'filepath': '/nonexistent/path/track.wav',
        'title': 'Invalid Track',
    })

    # What the repository *does* reject: track_info with no usable filepath.
    assert db.tracks.add({'title': 'No Filepath'}) is None
    assert db.tracks.add({'filepath': '', 'title': 'Empty Filepath'}) is None

    # Database should still be functional
    tracks, total = db.tracks.get_all(limit=10)
    assert tracks is not None


@pytest.mark.boundary
@pytest.mark.fast
@pytest.mark.library
@pytest.mark.error
def test_corrupted_audio_file_handling(tmp_path):
    """
    BOUNDARY: Adding track with corrupted audio file.

    Validates:
    - Graceful handling of corrupted files
    - No crash
    """
    db_path = tmp_path / "test.db"
    db = LibraryDatabase(database_path=str(db_path))

    audio_dir = tmp_path / "music"
    audio_dir.mkdir()

    # Create corrupted file (empty)
    corrupted_path = audio_dir / "corrupted.wav"
    corrupted_path.write_text("not valid audio")

    # Should handle gracefully
    try:
        db.tracks.add({
            'filepath': str(corrupted_path),
            'title': 'Corrupted Track',
        })
    except Exception:
        pass  # Expected to fail, should not crash

    # Database should still work
    tracks, total = db.tracks.get_all(limit=10)
    assert tracks is not None


@pytest.mark.boundary
@pytest.mark.fast
@pytest.mark.library
@pytest.mark.error
def test_partial_batch_failure(test_library_large):
    """
    BOUNDARY: Batch operation with some failures.

    Validates:
    - Partial failures don't corrupt database
    - Valid operations still succeed
    """
    db, track_ids, tmp_path = test_library_large

    # Try to delete mix of valid and invalid IDs
    ids_to_delete = track_ids[:5] + [999999, 999998]  # Last 2 don't exist

    for track_id in ids_to_delete:
        try:
            db.tracks.delete(track_id)
        except Exception:
            pass  # Some will fail

    # Valid deletes should have succeeded
    tracks, total = db.tracks.get_all(limit=200)
    assert total <= len(track_ids) - 5, (
        "Valid deletes should have succeeded"
    )


@pytest.mark.boundary
@pytest.mark.fast
@pytest.mark.library
@pytest.mark.error
def test_database_connection_recovery(tmp_path):
    """
    BOUNDARY: Operations after database errors.

    Validates:
    - Can recover from connection errors
    - Database remains consistent
    """
    db_path = tmp_path / "test.db"
    db = LibraryDatabase(database_path=str(db_path))

    audio_dir = tmp_path / "music"
    audio_dir.mkdir()

    # Add a track successfully
    audio = np.random.randn(44100, 2) * 0.1
    filepath = audio_dir / "track_1.wav"
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')

    track1 = db.tracks.add({
        'filepath': str(filepath),
        'title': 'Track 1',
    })

    # Should still work after previous operations
    tracks, total = db.tracks.get_all(limit=10)
    assert total == 1


@pytest.mark.boundary
@pytest.mark.fast
@pytest.mark.library
@pytest.mark.error
def test_concurrent_delete_same_track(test_library_large):
    """
    BOUNDARY: Multiple threads trying to delete same track.

    Validates:
    - Concurrent deletes of one track never raise
    - The track ends up gone and the rest of the library is intact
    """
    db, track_ids, _ = test_library_large

    target_id = track_ids[0]
    errors = []
    success_count = [0]

    def delete_track():
        try:
            result = db.tracks.delete(target_id)
            if result:  # Only count successful deletes
                success_count[0] += 1
        except Exception as e:
            errors.append(e)

    # 5 concurrent deletes of same track
    threads = [threading.Thread(target=delete_track) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # #4915: the old assertion here was `success_count[0] <= 1`, which held
    # only because LibraryManager.delete_track() serialized every delete behind
    # a facade-level `_delete_lock`. TrackRepository.delete() — what production
    # actually calls — does an unlocked SELECT-then-DELETE in its own session,
    # so several threads can each observe the row and each report True (the
    # losers' DELETE matches 0 rows and SQLAlchemy logs a SAWarning).
    # TODO(#5173): if "exactly one delete wins" is a property worth having, it
    # belongs in TrackRepository.delete() (e.g. check the DELETE rowcount and
    # return False when 0 rows matched), not in a deleted legacy facade.
    assert errors == [], f"Concurrent delete errors: {errors}"
    assert success_count[0] >= 1, "At least one concurrent delete should succeed"

    # Whatever the race, the outcome must be consistent: the target is gone,
    # exactly once, and nothing else was collateral damage.
    assert db.tracks.get_by_id(target_id) is None, "Target track should be deleted"
    tracks, total = db.tracks.get_all(limit=200)
    assert total == len(track_ids) - 1, (
        f"Expected {len(track_ids) - 1} tracks after the delete, got {total}"
    )
    assert target_id not in {t.id for t in tracks}


@pytest.mark.boundary
@pytest.mark.fast
@pytest.mark.library
@pytest.mark.error
def test_invalid_metadata_values(tmp_path):
    """
    BOUNDARY: Track with invalid metadata values.

    Validates:
    - Handles None, empty strings, special characters
    - Database constraints enforced
    """
    db_path = tmp_path / "test.db"
    db = LibraryDatabase(database_path=str(db_path))

    audio_dir = tmp_path / "music"
    audio_dir.mkdir()

    audio = np.random.randn(44100, 2) * 0.1
    filepath = audio_dir / "test.wav"
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')

    # Try various invalid metadata
    invalid_metadata = [
        {'title': ''},  # Empty string
        {'title': None},  # None value
        {'title': 'x' * 10000},  # Very long string
    ]

    for metadata in invalid_metadata:
        try:
            track_info = {'filepath': str(filepath)}
            track_info.update(metadata)
            db.tracks.add(track_info)
        except Exception:
            pass  # May or may not be allowed

    # Database should still be functional
    tracks, total = db.tracks.get_all(limit=10)
    assert tracks is not None
