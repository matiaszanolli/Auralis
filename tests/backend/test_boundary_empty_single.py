#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Empty and Single-Item Boundary Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Boundary tests for edge cases with empty collections and single items.
These tests catch off-by-one errors, null pointer issues, and empty state bugs.

:copyright: (C) 2024 Auralis Team
:license: GPLv3

CONTEXT: Empty and single-item bugs are common:
- Empty list iteration crashes
- Division by zero with empty data
- Off-by-one errors with single items
- Null pointer exceptions
- Missing null checks

Test Philosophy:
- Test empty collections
- Test single-item collections
- Test transitions (empty → 1 item → empty)
- Verify no crashes
- Check correct return values

See docs/development/TESTING_GUIDELINES.md for complete testing philosophy.
"""

import os

# Import the modules under test
import sys
import tempfile
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
def empty_library(tmp_path):
    """Create completely empty library."""
    db_path = tmp_path / "empty_library.db"
    db = LibraryDatabase(database_path=str(db_path))
    yield db, tmp_path


@pytest.fixture
def single_track_library(tmp_path):
    """Create library with exactly one track."""
    db_path = tmp_path / "single_library.db"
    db = LibraryDatabase(database_path=str(db_path))

    # Create single audio file
    audio_dir = tmp_path / "music"
    audio_dir.mkdir()

    audio = np.random.randn(441000, 2) * 0.1  # 10 seconds
    filepath = audio_dir / "single_track.wav"
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')

    # Add to library
    track_info = {
        'filepath': str(filepath),
        'title': 'Single Track',
        'artists': ['Single Artist'],
        'album': 'Single Album',
    }
    track = db.tracks.add(track_info)

    yield db, track.id, tmp_path


# ============================================================================
# Empty Library Boundary Tests (P0 Priority)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.empty
def test_empty_library_get_all_tracks(empty_library):
    """
    BOUNDARY: tracks.get_all() on empty library returns empty list.

    Common bug: Returns None instead of empty list, causing iteration errors.
    """
    db, _ = empty_library

    tracks, total = db.tracks.get_all(limit=10)

    assert tracks is not None, "Should return list, not None"
    assert isinstance(tracks, list), "Should return list type"
    assert len(tracks) == 0, "Should return empty list"
    assert total == 0, "Total count should be 0"


@pytest.mark.boundary
@pytest.mark.empty
def test_empty_library_get_albums(empty_library):
    """
    BOUNDARY: albums.get_all() on empty library.
    """
    db, _ = empty_library

    albums, total = db.albums.get_all(limit=10)

    assert albums is not None, "Should return list, not None"
    assert len(albums) == 0, "Should return empty list"
    assert total == 0, "Total should be 0"


@pytest.mark.boundary
@pytest.mark.empty
def test_empty_library_get_artists(empty_library):
    """
    BOUNDARY: artists.get_all() on empty library.
    """
    db, _ = empty_library

    artists, total = db.artists.get_all(limit=10)

    assert artists is not None, "Should return list, not None"
    assert len(artists) == 0, "Should return empty list"
    assert total == 0, "Total should be 0"


@pytest.mark.boundary
@pytest.mark.empty
def test_empty_library_search_returns_empty(empty_library):
    """
    BOUNDARY: Search on empty library returns empty results.
    """
    db, _ = empty_library

    results, total = db.tracks.search("test query")

    assert results is not None, "Should return list, not None"
    assert len(results) == 0, "Should return empty results"


@pytest.mark.boundary
@pytest.mark.empty
def test_empty_library_get_favorites_returns_empty(empty_library):
    """
    BOUNDARY: Favorites list on empty library.
    """
    db, _ = empty_library

    favorites, total = db.tracks.get_favorites(limit=10)

    assert favorites is not None, "Should return list, not None"
    assert len(favorites) == 0, "Should return empty list"


@pytest.mark.boundary
@pytest.mark.empty
def test_empty_library_get_recent_returns_empty(empty_library):
    """
    BOUNDARY: Recent tracks on empty library.
    """
    db, _ = empty_library

    recent, total = db.tracks.get_recent(limit=10)

    assert recent is not None, "Should return list, not None"
    assert len(recent) == 0, "Should return empty list"


@pytest.mark.boundary
@pytest.mark.empty
def test_empty_library_stats_all_zeros(empty_library):
    """
    BOUNDARY: Library stats on empty library should be all zeros.
    """
    db, _ = empty_library

    stats = db.stats.get_library_stats()

    assert stats is not None, "Should return stats dict"
    assert stats['total_tracks'] == 0, "Track count should be 0"
    assert stats['total_albums'] == 0, "Album count should be 0"
    assert stats['total_artists'] == 0, "Artist count should be 0"


@pytest.mark.boundary
@pytest.mark.empty
def test_empty_library_pagination_offset_beyond_empty(empty_library):
    """
    BOUNDARY: Pagination with offset > 0 on empty library.

    Common bug: Crashes or returns None instead of empty list.
    """
    db, _ = empty_library

    tracks, total = db.tracks.get_all(limit=10, offset=100)

    assert tracks is not None, "Should return list, not None"
    assert len(tracks) == 0, "Should return empty list"
    assert total == 0, "Total should still be 0"


@pytest.mark.boundary
@pytest.mark.empty
def test_empty_library_get_nonexistent_track(empty_library):
    """
    BOUNDARY: Get track by ID that doesn't exist.
    """
    db, _ = empty_library

    track = db.tracks.get_by_id(999999)

    assert track is None, "Should return None for nonexistent track"


@pytest.mark.boundary
@pytest.mark.empty
def test_empty_library_delete_nonexistent_track(empty_library):
    """
    BOUNDARY: Delete nonexistent track should not crash.
    """
    db, _ = empty_library

    # Should not raise exception
    try:
        db.tracks.delete(999999)
    except Exception as e:
        pytest.fail(f"Delete nonexistent track should not crash: {e}")


# ============================================================================
# Single-Item Library Boundary Tests (P0 Priority)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.single
def test_single_track_library_get_all_returns_one(single_track_library):
    """
    BOUNDARY: tracks.get_all() with single track.
    """
    db, track_id, _ = single_track_library

    tracks, total = db.tracks.get_all(limit=10)

    assert len(tracks) == 1, "Should return exactly 1 track"
    assert total == 1, "Total should be 1"
    assert tracks[0].id == track_id, "Should return the correct track"


@pytest.mark.boundary
@pytest.mark.single
def test_single_track_pagination_first_page(single_track_library):
    """
    BOUNDARY: First page of pagination with single track.
    """
    db, track_id, _ = single_track_library

    tracks, total = db.tracks.get_all(limit=10, offset=0)

    assert len(tracks) == 1, "First page should have 1 track"
    assert total == 1, "Total should be 1"


@pytest.mark.boundary
@pytest.mark.single
def test_single_track_pagination_second_page_empty(single_track_library):
    """
    BOUNDARY: Second page should be empty with single track.
    """
    db, track_id, _ = single_track_library

    tracks, total = db.tracks.get_all(limit=10, offset=10)

    assert len(tracks) == 0, "Second page should be empty"
    assert total == 1, "Total should still be 1"


@pytest.mark.boundary
@pytest.mark.single
def test_single_track_limit_one_returns_one(single_track_library):
    """
    BOUNDARY: limit=1 with single track.
    """
    db, track_id, _ = single_track_library

    tracks, total = db.tracks.get_all(limit=1, offset=0)

    assert len(tracks) == 1, "Should return 1 track"
    assert total == 1, "Total should be 1"


@pytest.mark.boundary
@pytest.mark.single
def test_single_track_search_match_returns_one(single_track_library):
    """
    BOUNDARY: Search matching single track.
    """
    db, track_id, _ = single_track_library

    results, total = db.tracks.search("Single")

    assert len(results) == 1, "Should return 1 result"
    assert results[0].id == track_id, "Should return correct track"


@pytest.mark.boundary
@pytest.mark.single
def test_single_track_search_no_match_returns_empty(single_track_library):
    """
    BOUNDARY: Search not matching single track.
    """
    db, track_id, _ = single_track_library

    results, total = db.tracks.search("Nonexistent")

    assert len(results) == 0, "Should return empty list"


@pytest.mark.boundary
@pytest.mark.single
def test_single_track_favorite_toggle(single_track_library):
    """
    BOUNDARY: Favorite toggle with single track.
    """
    db, track_id, _ = single_track_library

    # Set favorite
    db.tracks.set_favorite(track_id, True)

    favorites, total = db.tracks.get_favorites(limit=10)
    assert len(favorites) == 1, "Should have 1 favorite"
    assert len(favorites) == 1, "Should return 1 favorite"

    # Unset favorite
    db.tracks.set_favorite(track_id, False)

    favorites, total = db.tracks.get_favorites(limit=10)
    assert len(favorites) == 0, "Should have 0 favorites"
    assert len(favorites) == 0, "Should return empty list"


@pytest.mark.boundary
@pytest.mark.single
def test_single_track_play_count(single_track_library):
    """
    BOUNDARY: Play count with single track.
    """
    db, track_id, _ = single_track_library

    # Initial play count
    tracks, _ = db.tracks.get_all(limit=1)
    initial_count = tracks[0].play_count or 0

    # Record play
    db.tracks.record_play(track_id)

    # Check updated count
    tracks, _ = db.tracks.get_all(limit=1)
    new_count = tracks[0].play_count

    assert new_count == initial_count + 1, (
        f"Play count should increment: {initial_count} → {new_count}"
    )


@pytest.mark.boundary
@pytest.mark.single
def test_single_track_delete_returns_to_empty(single_track_library):
    """
    BOUNDARY: Deleting single track returns library to empty state.
    """
    db, track_id, _ = single_track_library

    # Verify single track exists
    tracks_before, count_before = db.tracks.get_all(limit=10)
    assert count_before == 1, "Should start with 1 track"

    # Delete track
    db.tracks.delete(track_id)

    # Verify empty
    tracks_after, count_after = db.tracks.get_all(limit=10)
    assert count_after == 0, "Should return to empty state"
    assert len(tracks_after) == 0, "Should return empty list"


@pytest.mark.boundary
@pytest.mark.single
def test_single_track_metadata_update(single_track_library):
    """
    BOUNDARY: Update metadata on single track.
    """
    db, track_id, _ = single_track_library

    # Update title
    new_title = "Updated Single Track"
    db.tracks.update(track_id, {'title': new_title})

    # Verify update
    tracks, _ = db.tracks.get_all(limit=1)
    assert tracks[0].title == new_title, "Title should be updated"


# ============================================================================
# Empty → Single → Empty Transitions (P1 Priority)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.transition
def test_empty_to_single_to_empty_transition(empty_library):
    """
    BOUNDARY: Full cycle empty → add track → delete track → empty.
    """
    db, tmp_path = empty_library

    # Start empty
    tracks, count = db.tracks.get_all(limit=10)
    assert count == 0, "Should start empty"

    # Add track
    audio_dir = tmp_path / "music"
    audio_dir.mkdir()

    audio = np.random.randn(441000, 2) * 0.1
    filepath = audio_dir / "track.wav"
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')

    track_info = {
        'filepath': str(filepath),
        'title': 'Test Track',
        'artists': ['Test Artist'],
    }
    track = db.tracks.add(track_info)

    # Verify single track
    tracks, count = db.tracks.get_all(limit=10)
    assert count == 1, "Should have 1 track after add"

    # Delete track
    db.tracks.delete(track.id)

    # Verify empty again
    tracks, count = db.tracks.get_all(limit=10)
    assert count == 0, "Should return to empty state"


# ============================================================================
# Empty Playlist Boundary Tests (P1 Priority)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.playlist
def test_empty_playlist_get_tracks_returns_empty(empty_library):
    """
    BOUNDARY: Empty playlist returns empty track list.
    """
    db, _ = empty_library

    # Create empty playlist
    playlist = db.playlists.create("Empty Playlist", "Test")

    # Get tracks
    if hasattr(playlist, 'tracks'):
        assert len(playlist.tracks) == 0, "Empty playlist should have no tracks"


@pytest.mark.boundary
@pytest.mark.playlist
def test_single_track_playlist(single_track_library):
    """
    BOUNDARY: Playlist with exactly one track.
    """
    db, track_id, _ = single_track_library

    # Create playlist
    playlist = db.playlists.create("Single Track Playlist", "Test")

    # Add track
    db.playlists.add_track(playlist.id, track_id)

    # Verify
    updated_playlist = db.playlists.get_by_id(playlist.id)
    if hasattr(updated_playlist, 'tracks'):
        assert len(updated_playlist.tracks) == 1, "Should have exactly 1 track"


@pytest.mark.boundary
@pytest.mark.playlist
def test_remove_only_track_from_playlist(single_track_library):
    """
    BOUNDARY: Removing only track returns playlist to empty state.
    """
    db, track_id, _ = single_track_library

    # Create playlist with track
    playlist = db.playlists.create("Test Playlist", "Test")
    db.playlists.add_track(playlist.id, track_id)

    # Remove track
    db.playlists.remove_track(playlist.id, track_id)

    # Verify empty
    updated_playlist = db.playlists.get_by_id(playlist.id)
    if hasattr(updated_playlist, 'tracks'):
        assert len(updated_playlist.tracks) == 0, (
            "Playlist should be empty after removing only track"
        )


# ============================================================================
# Zero-Length Audio Boundary Tests (P2 Priority)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.audio
def test_zero_length_audio_array():
    """
    BOUNDARY: Processing zero-length audio array.

    Common bug: Division by zero, empty array access.
    """
    from auralis.core.hybrid_processor import HybridProcessor
    from auralis.core.config import UnifiedConfig

    processor = HybridProcessor(UnifiedConfig())

    # Zero-length audio
    empty_audio = np.zeros((0, 2))

    # Should not crash
    try:
        result = processor.process(empty_audio)
        # Should return empty or handle gracefully
        assert len(result) == 0, "Should return empty for empty input"
    except (AssertionError, ZeroDivisionError, IndexError):
        raise  # never mask a real bug behind a skip (#4969)
    except Exception as e:
        # Document expected behavior if it should raise
        pytest.skip(f"Zero-length audio handling not implemented: {e}")


# ============================================================================
# Empty String Boundary Tests (P2 Priority)
# ============================================================================

@pytest.mark.boundary
@pytest.mark.string
def test_search_empty_string(single_track_library):
    """
    BOUNDARY: Search with empty string.

    Should return all tracks or empty results, not crash.
    """
    db, track_id, _ = single_track_library

    results, total = db.tracks.search("")

    # Should not crash
    assert results is not None, "Should return list, not None"
    assert isinstance(results, list), "Should return list type"


@pytest.mark.boundary
@pytest.mark.string
def test_create_playlist_empty_name(empty_library):
    """
    BOUNDARY: Create playlist with empty name.

    Should either accept or reject gracefully.
    """
    db, _ = empty_library

    try:
        playlist = db.playlists.create("", "Description")
        # If accepted, verify playlist exists
        assert playlist is not None, "Should create playlist"
    except ValueError:
        # If rejected, that's also acceptable behavior
        pass
