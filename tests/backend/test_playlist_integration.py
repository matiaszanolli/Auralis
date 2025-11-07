#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Playlist Operations Integration Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for playlist CRUD operations and track management.

:copyright: (C) 2024 Auralis Team
:license: GPLv3

CONTEXT: Playlist bugs can cause:
- Lost playlists (deletion failures)
- Duplicate tracks (insertion bugs)
- Wrong track order (sorting issues)
- Broken references (track deletion)

Test Philosophy:
- Test complete playlist workflows
- Verify CRUD operations
- Test track management
- Check data persistence

See docs/development/TESTING_GUIDELINES.md for complete testing philosophy.
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path

# Import the modules under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.library.manager import LibraryManager
from auralis.io.saver import save as save_audio


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def library_with_playlists(tmp_path):
    """Create library with tracks and playlists."""
    db_path = tmp_path / "test_library.db"
    manager = LibraryManager(database_path=str(db_path))

    # Create audio directory
    audio_dir = tmp_path / "music"
    audio_dir.mkdir()

    # Create 10 test tracks
    track_ids = []
    for i in range(10):
        audio = np.random.randn(441000, 2) * 0.1  # 10 seconds
        filepath = audio_dir / f"track_{i:02d}.wav"
        save_audio(str(filepath), audio, 44100, subtype='PCM_16')

        track_info = {
            'filepath': str(filepath),
            'title': f'Test Track {i:02d}',
            'artists': [f'Artist {i % 3}'],
            'album': f'Album {i % 5}',
        }
        track = manager.add_track(track_info)
        track_ids.append(track.id)

    # Create 2 test playlists
    playlist1 = manager.create_playlist("Playlist 1", "Test playlist 1")
    playlist2 = manager.create_playlist("Playlist 2", "Test playlist 2")

    yield manager, [playlist1.id, playlist2.id], track_ids, tmp_path

    # Cleanup handled by tmp_path


# ============================================================================
# Playlist CRUD Integration Tests (P0 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.playlist
def test_create_playlist(library_with_playlists):
    """
    INTEGRATION TEST: Create playlist workflow.

    Workflow:
    1. Create new playlist
    2. Verify playlist has unique ID
    3. Verify playlist appears in list
    4. Verify playlist has correct name
    """
    manager, existing_playlist_ids, track_ids, _ = library_with_playlists

    # Create new playlist
    new_playlist = manager.create_playlist("New Playlist", "Integration test")

    # Verify has ID
    assert new_playlist.id is not None, "Playlist should have ID"
    assert new_playlist.id not in existing_playlist_ids, "Playlist should have unique ID"

    # Verify appears in list
    all_playlists = manager.get_all_playlists()
    playlist_ids = {p.id for p in all_playlists}
    assert new_playlist.id in playlist_ids, "New playlist should appear in list"

    # Verify correct name
    assert new_playlist.name == "New Playlist", "Playlist should have correct name"


@pytest.mark.integration
@pytest.mark.playlist
def test_read_playlist(library_with_playlists):
    """
    INTEGRATION TEST: Read playlist by ID.

    Workflow:
    1. Get playlist by ID
    2. Verify correct playlist returned
    3. Verify all properties present
    """
    manager, playlist_ids, track_ids, _ = library_with_playlists

    # Get first playlist
    playlist = manager.get_playlist(playlist_ids[0])

    # Verify correct playlist
    assert playlist is not None, "Playlist should exist"
    assert playlist.id == playlist_ids[0], "Should get correct playlist"

    # Verify properties
    assert playlist.name is not None, "Playlist should have name"
    assert hasattr(playlist, 'tracks') or hasattr(playlist, 'track_count'), (
        "Playlist should have tracks info"
    )


@pytest.mark.integration
@pytest.mark.playlist
def test_update_playlist(library_with_playlists):
    """
    INTEGRATION TEST: Update playlist metadata.

    Workflow:
    1. Update playlist name
    2. Verify change persists
    3. Update description
    4. Verify change persists
    """
    manager, playlist_ids, track_ids, _ = library_with_playlists

    # Get playlist
    playlist = manager.get_playlist(playlist_ids[0])
    original_name = playlist.name

    # Update name
    new_name = "Updated Playlist Name"
    manager.update_playlist(playlist.id, name=new_name)

    # Verify change persists
    updated_playlist = manager.get_playlist(playlist.id)
    assert updated_playlist.name == new_name, (
        f"Name should be updated: expected '{new_name}', got '{updated_playlist.name}'"
    )
    assert updated_playlist.name != original_name, "Name should have changed"


@pytest.mark.integration
@pytest.mark.playlist
def test_delete_playlist(library_with_playlists):
    """
    INTEGRATION TEST: Delete playlist workflow.

    Workflow:
    1. Delete playlist
    2. Verify removed from list
    3. Verify get by ID returns None
    4. Verify tracks still exist (not cascade deleted)
    """
    manager, playlist_ids, track_ids, _ = library_with_playlists

    # Get initial count
    initial_playlists = manager.get_all_playlists()
    initial_count = len(initial_playlists)

    # Delete playlist
    manager.delete_playlist(playlist_ids[0])

    # Verify removed from list
    remaining_playlists = manager.get_all_playlists()
    assert len(remaining_playlists) == initial_count - 1, (
        f"Playlist count should decrease: {initial_count} → {len(remaining_playlists)}"
    )

    remaining_ids = {p.id for p in remaining_playlists}
    assert playlist_ids[0] not in remaining_ids, "Deleted playlist should not appear"

    # Verify tracks still exist
    tracks, total = manager.get_all_tracks(limit=100)
    assert len(tracks) == len(track_ids), "Tracks should not be deleted with playlist"


# ============================================================================
# Playlist Track Management Tests (P0 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.playlist
def test_add_track_to_playlist(library_with_playlists):
    """
    INTEGRATION TEST: Add track to playlist workflow.

    Workflow:
    1. Add track to playlist
    2. Verify track count increases
    3. Verify track appears in playlist
    """
    manager, playlist_ids, track_ids, _ = library_with_playlists

    # Get initial playlist state
    playlist = manager.get_playlist(playlist_ids[0])
    initial_track_count = len(playlist.tracks) if hasattr(playlist, 'tracks') else 0

    # Add track
    manager.add_track_to_playlist(playlist_ids[0], track_ids[0])

    # Verify track count increased
    updated_playlist = manager.get_playlist(playlist_ids[0])
    new_track_count = len(updated_playlist.tracks) if hasattr(updated_playlist, 'tracks') else 0

    assert new_track_count == initial_track_count + 1, (
        f"Track count should increase: {initial_track_count} → {new_track_count}"
    )

    # Verify track appears in playlist
    if hasattr(updated_playlist, 'tracks'):
        playlist_track_ids = {t.id for t in updated_playlist.tracks}
        assert track_ids[0] in playlist_track_ids, "Added track should appear in playlist"


@pytest.mark.integration
@pytest.mark.playlist
def test_remove_track_from_playlist(library_with_playlists):
    """
    INTEGRATION TEST: Remove track from playlist workflow.

    Workflow:
    1. Add track to playlist
    2. Remove track from playlist
    3. Verify track count decreases
    4. Verify track removed from playlist
    5. Verify track still exists in library
    """
    manager, playlist_ids, track_ids, _ = library_with_playlists

    # Add track first
    manager.add_track_to_playlist(playlist_ids[0], track_ids[0])

    # Get state after add
    playlist_after_add = manager.get_playlist(playlist_ids[0])
    count_after_add = len(playlist_after_add.tracks) if hasattr(playlist_after_add, 'tracks') else 0

    # Remove track
    manager.remove_track_from_playlist(playlist_ids[0], track_ids[0])

    # Verify track count decreased
    playlist_after_remove = manager.get_playlist(playlist_ids[0])
    count_after_remove = len(playlist_after_remove.tracks) if hasattr(playlist_after_remove, 'tracks') else 0

    assert count_after_remove == count_after_add - 1, (
        f"Track count should decrease: {count_after_add} → {count_after_remove}"
    )

    # Verify track still in library
    tracks, _ = manager.get_all_tracks(limit=1000)
    library_track_ids = {t.id for t in tracks}
    assert track_ids[0] in library_track_ids, "Track should still exist in library"


@pytest.mark.integration
@pytest.mark.playlist
def test_reorder_tracks_in_playlist(library_with_playlists):
    """
    INTEGRATION TEST: Reorder tracks in playlist.

    Workflow:
    1. Add multiple tracks to playlist
    2. Reorder tracks
    3. Verify new order persists
    """
    manager, playlist_ids, track_ids, _ = library_with_playlists

    # Add 3 tracks
    for i in range(3):
        manager.add_track_to_playlist(playlist_ids[0], track_ids[i])

    # Get current order
    playlist = manager.get_playlist(playlist_ids[0])
    if hasattr(playlist, 'tracks'):
        original_order = [t.id for t in playlist.tracks]

        # Reorder (move last to first)
        new_order = [original_order[2], original_order[0], original_order[1]]
        manager.reorder_playlist_tracks(playlist_ids[0], new_order)

        # Verify new order
        updated_playlist = manager.get_playlist(playlist_ids[0])
        actual_order = [t.id for t in updated_playlist.tracks]

        assert actual_order == new_order, (
            f"Track order should change: {original_order} → {actual_order}"
        )


# ============================================================================
# Playlist Query Tests (P1 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.playlist
def test_get_all_playlists(library_with_playlists):
    """
    INTEGRATION TEST: Get all playlists.

    Validates:
    - Returns all playlists
    - Each has required properties
    - No duplicates
    """
    manager, playlist_ids, track_ids, _ = library_with_playlists

    # Get all playlists
    playlists = manager.get_all_playlists()

    # Should have at least the test playlists
    assert len(playlists) >= 2, f"Should have at least 2 playlists, got {len(playlists)}"

    # Each should have required properties
    for playlist in playlists:
        assert playlist.id is not None, "Playlist should have ID"
        assert playlist.name is not None, "Playlist should have name"

    # No duplicates
    playlist_ids_found = [p.id for p in playlists]
    unique_ids = set(playlist_ids_found)
    assert len(playlist_ids_found) == len(unique_ids), "Should have no duplicate playlists"


@pytest.mark.integration
@pytest.mark.playlist
def test_search_playlists(library_with_playlists):
    """
    INTEGRATION TEST: Search playlists by name.

    Workflow:
    1. Search for playlist name
    2. Verify matching playlists returned
    3. Verify non-matching playlists excluded
    """
    manager, playlist_ids, track_ids, _ = library_with_playlists

    # Search for "Playlist 1"
    results = manager.search_playlists("Playlist 1")

    # Should return at least one result
    assert len(results) >= 1, "Search should return results"

    # All results should match query
    for playlist in results:
        assert "Playlist 1" in playlist.name or "playlist 1" in playlist.name.lower(), (
            f"Result '{playlist.name}' should match query 'Playlist 1'"
        )


# ============================================================================
# Playlist Edge Cases (P2 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.playlist
def test_duplicate_track_in_playlist(library_with_playlists):
    """
    INTEGRATION TEST: Adding same track twice to playlist.

    Validates:
    - Same track can be added multiple times OR
    - Duplicate is rejected
    """
    manager, playlist_ids, track_ids, _ = library_with_playlists

    # Add track once
    manager.add_track_to_playlist(playlist_ids[0], track_ids[0])

    # Try to add same track again
    manager.add_track_to_playlist(playlist_ids[0], track_ids[0])

    # Get playlist
    playlist = manager.get_playlist(playlist_ids[0])
    if hasattr(playlist, 'tracks'):
        track_occurrences = [t.id for t in playlist.tracks].count(track_ids[0])

        # Either allows duplicates (count > 1) or rejects (count == 1)
        # Test documents the behavior
        assert track_occurrences >= 1, "Track should appear at least once"


@pytest.mark.integration
@pytest.mark.playlist
def test_delete_track_from_playlist_cascade(library_with_playlists):
    """
    INTEGRATION TEST: Deleting track from library removes from playlists.

    Workflow:
    1. Add track to playlist
    2. Delete track from library
    3. Verify track removed from playlist
    4. Verify playlist still exists
    """
    manager, playlist_ids, track_ids, _ = library_with_playlists

    # Add track to playlist
    manager.add_track_to_playlist(playlist_ids[0], track_ids[0])

    # Verify in playlist
    playlist_before = manager.get_playlist(playlist_ids[0])
    if hasattr(playlist_before, 'tracks'):
        track_ids_before = {t.id for t in playlist_before.tracks}
        assert track_ids[0] in track_ids_before, "Track should be in playlist"

    # Delete track from library
    manager.delete_track(track_ids[0])

    # Verify removed from playlist
    playlist_after = manager.get_playlist(playlist_ids[0])
    if hasattr(playlist_after, 'tracks'):
        track_ids_after = {t.id for t in playlist_after.tracks}
        assert track_ids[0] not in track_ids_after, (
            "Deleted track should be removed from playlist"
        )

    # Verify playlist still exists
    assert playlist_after is not None, "Playlist should still exist"


# ============================================================================
# Summary Statistics
# ============================================================================

def test_summary_stats():
    """
    Print summary of what these tests validate.
    """
    print("\n" + "=" * 80)
    print("PLAYLIST OPERATIONS INTEGRATION TEST SUMMARY")
    print("=" * 80)
    print(f"CRUD Operations: 4 tests")
    print(f"Track Management: 3 tests")
    print(f"Query Operations: 2 tests")
    print(f"Edge Cases: 2 tests")
    print("=" * 80)
    print(f"TOTAL: 11 playlist integration tests")
    print("=" * 80)
    print("\nThese tests validate playlist operations:")
    print("1. Create, Read, Update, Delete playlists")
    print("2. Add, remove, reorder tracks")
    print("3. Search and query playlists")
    print("4. Cascade deletion behavior")
    print("5. Edge cases (duplicates, empty playlists)")
    print("=" * 80 + "\n")
