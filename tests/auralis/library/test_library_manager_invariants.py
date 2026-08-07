#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Library Database Invariant Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Critical invariant tests for LibraryDatabase (and the repositories it exposes)
that validate read-after-write consistency and data integrity properties.

:copyright: (C) 2024 Auralis Team
:license: GPLv3

CONTEXT: Library database bugs can cause:
- Stale reads (showing old metadata after updates)
- Inconsistent counts (total ≠ actual count)
- Lost playlists or favorites
- Duplicate tracks or albums
- Database corruption

These tests validate properties that MUST always hold for the library database.

Test Philosophy:
- Test invariants (properties that must always hold)
- Test behavior, not implementation
- Focus on defect detection
- Integration tests for real database operations

See docs/development/TESTING_GUIDELINES.md for complete testing philosophy.
"""

import os

# Import the modules under test
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auralis.io.saver import save as save_audio
from auralis.library.database import LibraryDatabase
from auralis.library.models import Album, Artist, Track

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_db():
    """Create temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_library.db")
    db = LibraryDatabase(database_path=db_path)

    yield db, temp_dir

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def populated_db(test_db):
    """Create a library database populated with test tracks."""
    db, temp_dir = test_db

    # Create test audio directory
    audio_dir = os.path.join(temp_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    # Create 20 test tracks
    for i in range(20):
        # Create minimal audio file
        audio = np.random.randn(44100, 2)  # 1 second stereo
        filepath = os.path.join(audio_dir, f"track_{i:02d}.wav")
        save_audio(filepath, audio, 44100, subtype='PCM_16')

        # Add to database
        track_info = {
            'filepath': filepath,
            'title': f'Track {i:02d}',
            'artists': [f'Artist {i % 5}'],  # 5 artists total
            'album': f'Album {i % 10}',      # 10 albums total
            'duration': 1.0,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'track_number': (i % 10) + 1,
            'year': 2020 + (i % 3),
        }
        db.tracks.add(track_info)

    return db, temp_dir


# ============================================================================
# Read-After-Write Consistency Invariants (P0 Priority)
# ============================================================================

@pytest.mark.invariant
@pytest.mark.integration
@pytest.mark.fast
@pytest.mark.library
def test_track_list_reflects_added_track(populated_db):
    """
    CRITICAL INVARIANT: Adding a track must be visible to subsequent reads.

    After adding a track, list queries must return fresh data including
    the new track.
    """
    db, temp_dir = populated_db

    # Get initial count
    initial_tracks, initial_count = db.tracks.get_all(limit=100)

    # Add new track
    audio_dir = os.path.join(temp_dir, "audio")
    new_filepath = os.path.join(audio_dir, "new_track.wav")
    audio = np.random.randn(44100, 2)
    save_audio(new_filepath, audio, 44100, subtype='PCM_16')

    track_info = {
        'filepath': new_filepath,
        'title': 'New Track',
        'artists': ['New Artist'],
        'album': 'New Album',
    }
    db.tracks.add(track_info)

    # Get count again (should reflect new track)
    new_tracks, new_count = db.tracks.get_all(limit=100)

    assert new_count == initial_count + 1, (
        f"Added track not visible to a later read: "
        f"expected {initial_count + 1} tracks, got {new_count}"
    )
    assert len(new_tracks) == len(initial_tracks) + 1, (
        "Track list not updated after add"
    )


@pytest.mark.integration
def test_track_list_reflects_deleted_track(populated_db):
    """
    INVARIANT: Deleting a track must be visible to subsequent reads.
    """
    db, _ = populated_db

    # Get initial tracks
    initial_tracks, initial_count = db.tracks.get_all(limit=100)
    first_track_id = initial_tracks[0].id

    # Delete first track
    db.tracks.delete(first_track_id)

    # Get tracks again (should reflect deletion)
    new_tracks, new_count = db.tracks.get_all(limit=100)

    assert new_count == initial_count - 1, (
        f"Deleted track still counted by a later read: "
        f"expected {initial_count - 1} tracks, got {new_count}"
    )

    # Deleted track should not appear in results
    track_ids = {t.id for t in new_tracks}
    assert first_track_id not in track_ids, (
        "Deleted track still appears in query results"
    )


@pytest.mark.integration
def test_track_list_reflects_updated_metadata(populated_db):
    """
    INVARIANT: Updating track metadata must be visible to subsequent reads.
    """
    db, _ = populated_db

    # Get initial tracks
    tracks, _ = db.tracks.get_all(limit=100)
    first_track = tracks[0]
    original_title = first_track.title

    # Update metadata
    new_title = "Updated Title"
    db.tracks.update(first_track.id, {'title': new_title})

    # Get track again (should have new title)
    updated_tracks, _ = db.tracks.get_all(limit=100)
    updated_track = next(t for t in updated_tracks if t.id == first_track.id)

    assert updated_track.title == new_title, (
        f"Metadata update not visible to a later read: "
        f"expected '{new_title}', got '{updated_track.title}'"
    )
    assert updated_track.title != original_title, (
        "Metadata update not reflected in query results"
    )


@pytest.mark.integration
def test_favorites_reflect_toggled_favorite(populated_db):
    """
    INVARIANT: Toggling favorite status must be visible in the favorites list.
    """
    db, _ = populated_db

    # Get initial favorites count
    initial_favorites, initial_fav_count = db.tracks.get_favorites(limit=100)

    # Get first track and toggle favorite
    tracks, _ = db.tracks.get_all(limit=1)
    track_id = tracks[0].id

    db.tracks.set_favorite(track_id, True)

    # Get favorites again
    new_favorites, new_fav_count = db.tracks.get_favorites(limit=100)

    assert new_fav_count == initial_fav_count + 1, (
        f"Favorite toggle not visible in favorites list: "
        f"expected {initial_fav_count + 1}, got {new_fav_count}"
    )


# ============================================================================
# Database Consistency Invariants (P0 Priority)
# ============================================================================

@pytest.mark.integration
def test_track_count_matches_actual_tracks(populated_db):
    """
    CRITICAL INVARIANT: get_library_stats() count must match actual track count.

    COUNT(*) must equal the number of tracks you can actually retrieve.
    """
    db, _ = populated_db

    # Get stats
    stats = db.stats.get_library_stats()
    reported_count = stats['total_tracks']

    # Get all tracks
    all_tracks, actual_count = db.tracks.get_all(limit=1000)

    assert reported_count == actual_count, (
        f"Stats count mismatch: stats reports {reported_count}, "
        f"but get_all_tracks reports {actual_count}"
    )
    assert reported_count == len(all_tracks), (
        f"Stats count mismatch: stats reports {reported_count}, "
        f"but actual track count is {len(all_tracks)}"
    )


@pytest.mark.integration
def test_album_count_matches_actual_albums(populated_db):
    """
    INVARIANT: Album count in stats must match actual album count.
    """
    db, _ = populated_db

    # Get stats
    stats = db.stats.get_library_stats()
    reported_count = stats['total_albums']

    # Get all albums
    all_albums, actual_count = db.albums.get_all(limit=1000)

    assert reported_count == actual_count, (
        f"Album count mismatch: stats={reported_count}, actual={actual_count}"
    )
    assert reported_count == len(all_albums), (
        f"Album count mismatch: stats={reported_count}, retrieved={len(all_albums)}"
    )


@pytest.mark.integration
def test_artist_count_matches_actual_artists(populated_db):
    """
    INVARIANT: Artist count in stats must match actual artist count.
    """
    db, _ = populated_db

    # Get stats
    stats = db.stats.get_library_stats()
    reported_count = stats['total_artists']

    # Get all artists
    all_artists, actual_count = db.artists.get_all(limit=1000)

    assert reported_count == actual_count, (
        f"Artist count mismatch: stats={reported_count}, actual={actual_count}"
    )


# ============================================================================
# Track Uniqueness Invariants (P0 Priority)
# ============================================================================

@pytest.mark.integration
def test_tracks_have_unique_ids(populated_db):
    """
    INVARIANT: All tracks must have unique IDs.

    Duplicate IDs would cause data corruption and retrieval errors.
    """
    db, _ = populated_db

    # Get all tracks
    tracks, _ = db.tracks.get_all(limit=1000)

    track_ids = [t.id for t in tracks]
    unique_ids = set(track_ids)

    assert len(track_ids) == len(unique_ids), (
        f"Duplicate track IDs found: {len(track_ids)} tracks, "
        f"{len(unique_ids)} unique IDs. "
        f"Duplicates: {[id for id in track_ids if track_ids.count(id) > 1]}"
    )


@pytest.mark.integration
def test_tracks_have_unique_filepaths(populated_db):
    """
    INVARIANT: All tracks must have unique filepaths.

    Same file should not be added twice to the library.
    """
    db, _ = populated_db

    # Get all tracks
    tracks, _ = db.tracks.get_all(limit=1000)

    filepaths = [t.filepath for t in tracks]
    unique_paths = set(filepaths)

    assert len(filepaths) == len(unique_paths), (
        f"Duplicate filepaths found: {len(filepaths)} tracks, "
        f"{len(unique_paths)} unique paths. "
        f"This suggests duplicate track entries for the same file."
    )


# ============================================================================
# Favorite Management Invariants (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_favorites_are_subset_of_all_tracks(populated_db):
    """
    INVARIANT: Favorite tracks must be a subset of all tracks.

    Can't have a favorite that doesn't exist in the library.
    """
    db, _ = populated_db

    # Mark some tracks as favorites
    tracks, _ = db.tracks.get_all(limit=5)
    for track in tracks:
        db.tracks.set_favorite(track.id, True)

    # Get all tracks and favorites
    all_tracks, _ = db.tracks.get_all(limit=1000)
    favorites, _ = db.tracks.get_favorites(limit=1000)

    all_track_ids = {t.id for t in all_tracks}
    favorite_ids = {t.id for t in favorites}

    assert favorite_ids.issubset(all_track_ids), (
        f"Favorites contain IDs not in library: {favorite_ids - all_track_ids}"
    )


@pytest.mark.integration
def test_favorite_toggle_is_idempotent(populated_db):
    """
    INVARIANT: Setting favorite=True twice should result in same state.

    Idempotent operations are essential for reliability.
    """
    db, _ = populated_db

    # Get a track
    tracks, _ = db.tracks.get_all(limit=1)
    track_id = tracks[0].id

    # Set favorite twice
    db.tracks.set_favorite(track_id, True)
    favorites_after_first, count1 = db.tracks.get_favorites(limit=1000)

    db.tracks.set_favorite(track_id, True)
    favorites_after_second, count2 = db.tracks.get_favorites(limit=1000)

    assert count1 == count2, (
        f"Favorite count changed after second set_favorite(True): "
        f"{count1} → {count2}"
    )


@pytest.mark.integration
def test_unfavorite_removes_from_favorites_list(populated_db):
    """
    INVARIANT: Setting favorite=False must remove track from favorites.
    """
    db, _ = populated_db

    # Get a track and favorite it
    tracks, _ = db.tracks.get_all(limit=1)
    track_id = tracks[0].id

    db.tracks.set_favorite(track_id, True)
    favorites_after_add, count_after_add = db.tracks.get_favorites(limit=1000)

    # Unfavorite it
    db.tracks.set_favorite(track_id, False)
    favorites_after_remove, count_after_remove = db.tracks.get_favorites(limit=1000)

    assert count_after_remove == count_after_add - 1, (
        f"Unfavorite didn't reduce count: {count_after_add} → {count_after_remove}"
    )

    favorite_ids = {t.id for t in favorites_after_remove}
    assert track_id not in favorite_ids, (
        "Unfavorited track still appears in favorites list"
    )


# ============================================================================
# Play Count Invariants (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_play_count_increments_correctly(populated_db):
    """
    INVARIANT: record_play() must increment play count by exactly 1.
    """
    db, _ = populated_db

    # Get a track
    tracks, _ = db.tracks.get_all(limit=1)
    track = tracks[0]
    initial_play_count = track.play_count or 0

    # Record a play
    db.tracks.record_play(track.id)

    # Get track again
    updated_tracks, _ = db.tracks.get_all(limit=1000)
    updated_track = next(t for t in updated_tracks if t.id == track.id)

    assert updated_track.play_count == initial_play_count + 1, (
        f"Play count increment incorrect: {initial_play_count} → {updated_track.play_count}"
    )


@pytest.mark.integration
def test_play_count_is_non_negative(populated_db):
    """
    INVARIANT: Play count must always be >= 0.
    """
    db, _ = populated_db

    # Get all tracks
    tracks, _ = db.tracks.get_all(limit=1000)

    for track in tracks:
        play_count = track.play_count or 0
        assert play_count >= 0, (
            f"Track {track.id} has negative play count: {play_count}"
        )


@pytest.mark.integration
def test_recent_tracks_ordered_by_last_played(populated_db):
    """
    INVARIANT: get_recent() must return tracks ordered by last_played DESC.
    """
    db, _ = populated_db

    # Play some tracks in order
    tracks, _ = db.tracks.get_all(limit=5)
    for track in tracks:
        db.tracks.record_play(track.id)
        import time
        time.sleep(0.01)  # Ensure different timestamps

    # Get recent tracks
    recent, _ = db.tracks.get_recent(limit=100)

    # Filter out tracks without last_played timestamps (shouldn't happen, but be safe)
    recent_with_timestamps = [t for t in recent if t.last_played is not None]

    if len(recent_with_timestamps) < 2:
        pytest.skip("Need at least 2 recent tracks with timestamps to test ordering")

    # Verify ordering
    for i in range(len(recent_with_timestamps) - 1):
        assert recent_with_timestamps[i].last_played >= recent_with_timestamps[i + 1].last_played, (
            f"Recent tracks not properly ordered: "
            f"track {i} played at {recent_with_timestamps[i].last_played}, "
            f"track {i+1} played at {recent_with_timestamps[i+1].last_played}"
        )


# ============================================================================
# Search Invariants (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_search_results_are_subset_of_all_tracks(populated_db):
    """
    INVARIANT: Search results must be a subset of all tracks.
    """
    db, _ = populated_db

    # Get all tracks
    all_tracks, _ = db.tracks.get_all(limit=1000)
    all_track_ids = {t.id for t in all_tracks}

    # Search for something
    search_results, _ = db.tracks.search("Track")
    search_ids = {t.id for t in search_results}

    assert search_ids.issubset(all_track_ids), (
        f"Search returned IDs not in library: {search_ids - all_track_ids}"
    )


@pytest.mark.integration
def test_search_returns_only_matching_tracks(populated_db):
    """
    INVARIANT: Search results must all match the query string.
    """
    db, _ = populated_db

    query = "Track 0"  # Should match "Track 00", "Track 01", ... "Track 09"

    results, _ = db.tracks.search(query)

    for track in results:
        # At least one field should contain the query (case-insensitive)
        matches = (
            query.lower() in track.title.lower() if track.title else False or
            query.lower() in track.album.lower() if track.album else False or
            any(query.lower() in artist.name.lower() for artist in track.artists)
        )
        assert matches, (
            f"Search result doesn't match query '{query}': "
            f"title='{track.title}', album='{track.album}'"
        )


# ============================================================================
# Deletion Cascading Invariants (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_deleting_track_removes_from_favorites(populated_db):
    """
    INVARIANT: Deleting a track must remove it from favorites.
    """
    db, _ = populated_db

    # Favorite a track
    tracks, _ = db.tracks.get_all(limit=1)
    track_id = tracks[0].id
    db.tracks.set_favorite(track_id, True)

    # Verify it's in favorites
    favorites, fav_count_before = db.tracks.get_favorites(limit=1000)
    assert any(t.id == track_id for t in favorites), "Track not in favorites after set_favorite"

    # Delete the track
    db.tracks.delete(track_id)

    # Verify it's removed from favorites
    favorites_after, fav_count_after = db.tracks.get_favorites(limit=1000)
    assert not any(t.id == track_id for t in favorites_after), (
        "Deleted track still appears in favorites"
    )
    assert fav_count_after < fav_count_before, (
        "Favorite count didn't decrease after deleting favorite track"
    )


@pytest.mark.integration
def test_deleting_track_removes_from_recent(populated_db):
    """
    INVARIANT: Deleting a track must remove it from recent tracks.
    """
    db, _ = populated_db

    # Play a track
    tracks, _ = db.tracks.get_all(limit=1)
    track_id = tracks[0].id
    db.tracks.record_play(track_id)

    # Verify it's in recent
    recent, _ = db.tracks.get_recent(limit=1000)
    assert any(t.id == track_id for t in recent), "Track not in recent after play"

    # Delete the track
    db.tracks.delete(track_id)

    # Verify it's removed from recent
    recent_after, _ = db.tracks.get_recent(limit=1000)
    assert not any(t.id == track_id for t in recent_after), (
        "Deleted track still appears in recent tracks"
    )


# ============================================================================
# Edge Cases (P2 Priority)
# ============================================================================

@pytest.mark.integration
def test_operations_on_empty_library(test_db):
    """
    INVARIANT: All operations should work on empty library (not crash).
    """
    db, _ = test_db

    # Get operations
    tracks, count = db.tracks.get_all(limit=10)
    assert len(tracks) == 0
    assert count == 0

    favorites, fav_count = db.tracks.get_favorites(limit=10)
    assert len(favorites) == 0
    assert fav_count == 0

    recent, recent_count = db.tracks.get_recent(limit=10)
    assert len(recent) == 0
    assert recent_count == 0

    search, search_count = db.tracks.search("test")
    assert len(search) == 0
    assert search_count == 0

    # Stats should return zeros
    stats = db.stats.get_library_stats()
    assert stats['total_tracks'] == 0
    assert stats['total_albums'] == 0
    assert stats['total_artists'] == 0


@pytest.mark.integration
def test_operations_on_nonexistent_track_id(populated_db):
    """
    INVARIANT: Operations on non-existent ID should handle gracefully.
    """
    db, _ = populated_db

    nonexistent_id = 999999

    # Should not crash, should return None or False
    try:
        db.tracks.set_favorite(nonexistent_id, True)
        db.tracks.record_play(nonexistent_id)
        db.tracks.delete(nonexistent_id)
        # If we get here, operations handled gracefully
    except Exception as e:
        pytest.fail(f"Operation on nonexistent ID should not raise exception: {e}")
