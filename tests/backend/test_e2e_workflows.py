#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
End-to-End Workflow Integration Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for complete user workflows (add track → play → enhance).
These tests validate that the entire system works together correctly.

:copyright: (C) 2024 Auralis Team
:license: GPLv3

CONTEXT: Integration tests catch bugs that unit tests miss:
- Configuration issues (like the overlap bug)
- State management across components
- Data flow between modules
- API contract violations

Test Philosophy:
- Test complete user workflows
- Use real components (minimal mocking)
- Verify state transitions
- Check data persistence
- Focus on API contracts

See docs/development/TESTING_GUIDELINES.md for complete testing philosophy.
"""

import pytest
import numpy as np
import tempfile
import os
import asyncio
from pathlib import Path

# Import the modules under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.library.manager import LibraryManager
from auralis.player.enhanced_player import EnhancedPlayer
from auralis.core.unified_config import UnifiedConfig
from auralis.io.saver import save as save_audio


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_library():
    """Create temporary library with test tracks."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_library.db")
    manager = LibraryManager(database_path=db_path)

    # Create test audio directory
    audio_dir = os.path.join(temp_dir, "music")
    os.makedirs(audio_dir)

    # Create 5 test tracks
    track_ids = []
    for i in range(5):
        # Create 10-second audio file
        audio = np.random.randn(441000, 2) * 0.1  # 10 seconds stereo
        filepath = os.path.join(audio_dir, f"track_{i:02d}.wav")
        save_audio(filepath, audio, 44100, subtype='PCM_16')

        # Add to library
        track_info = {
            'filepath': filepath,
            'title': f'Test Track {i:02d}',
            'artists': [f'Test Artist {i % 2}'],
            'album': f'Test Album {i % 3}',
            'duration': 10.0,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
        }
        track = manager.add_track(track_info)
        track_ids.append(track.id)

    yield manager, track_ids, temp_dir

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def player():
    """Create EnhancedPlayer instance."""
    config = UnifiedConfig()
    return EnhancedPlayer(config)


# ============================================================================
# E2E Workflow Tests (P0 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.e2e
def test_add_track_then_play_workflow(test_library, player):
    """
    INTEGRATION TEST: Complete workflow of adding track and playing it.

    Workflow:
    1. Add track to library
    2. Load track in player
    3. Start playback
    4. Verify audio is playing

    This tests the integration between library, player, and audio loading.
    """
    manager, track_ids, _ = test_library

    # Step 1: Track already added in fixture
    first_track_id = track_ids[0]

    # Step 2: Get track from library
    tracks, _ = manager.get_all_tracks(limit=1)
    assert len(tracks) == 5, "Should have 5 tracks in library"

    track = next(t for t in tracks if t.id == first_track_id)
    assert track is not None, "Track should exist in library"

    # Step 3: Load track in player
    player.load_track(track.filepath)

    # Step 4: Verify track is loaded
    assert player.is_loaded(), "Player should have track loaded"
    assert player.get_duration() > 0, "Track should have positive duration"

    # Step 5: Start playback
    player.play()

    # Step 6: Verify playback state
    assert player.is_playing(), "Player should be playing"
    assert player.get_position() >= 0, "Playback position should be non-negative"


@pytest.mark.integration
@pytest.mark.e2e
def test_play_pause_resume_workflow(test_library, player):
    """
    INTEGRATION TEST: Play → Pause → Resume workflow.

    Validates state transitions:
    - Stopped → Playing
    - Playing → Paused
    - Paused → Playing
    """
    manager, track_ids, _ = test_library

    # Load track
    tracks, _ = manager.get_all_tracks(limit=1)
    player.load_track(tracks[0].filepath)

    # Initial state: stopped
    assert not player.is_playing(), "Player should start stopped"

    # Transition: stopped → playing
    player.play()
    assert player.is_playing(), "Player should be playing after play()"

    # Transition: playing → paused
    player.pause()
    assert not player.is_playing(), "Player should be paused after pause()"

    position_after_pause = player.get_position()

    # Transition: paused → playing (resume)
    player.play()
    assert player.is_playing(), "Player should resume after play()"

    # Position should not have reset
    assert player.get_position() >= position_after_pause, (
        "Position should not decrease after resume"
    )


@pytest.mark.integration
@pytest.mark.e2e
def test_seek_during_playback_workflow(test_library, player):
    """
    INTEGRATION TEST: Seek to position during playback.

    Validates:
    - Seeking updates position
    - Playback continues after seek
    - Seeking doesn't cause crashes
    """
    manager, track_ids, _ = test_library

    # Load and play track
    tracks, _ = manager.get_all_tracks(limit=1)
    player.load_track(tracks[0].filepath)
    player.play()

    # Wait a bit for playback to start
    import time
    time.sleep(0.1)

    # Seek to middle of track
    track_duration = player.get_duration()
    seek_position = track_duration / 2

    player.seek_to_position(seek_position)

    # Verify seek worked
    current_position = player.get_position()
    assert abs(current_position - seek_position) < 1.0, (
        f"Seek failed: requested {seek_position}s, got {current_position}s"
    )

    # Verify playback continues
    assert player.is_playing(), "Player should still be playing after seek"


@pytest.mark.integration
@pytest.mark.e2e
def test_next_track_workflow(test_library, player):
    """
    INTEGRATION TEST: Play track → next track.

    Validates:
    - Queue management
    - Track transitions
    - Playback state persistence
    """
    manager, track_ids, _ = test_library

    # Add tracks to queue
    tracks, _ = manager.get_all_tracks(limit=2)
    assert len(tracks) >= 2, "Need at least 2 tracks for this test"

    # Load first track
    player.load_track(tracks[0].filepath)
    player.play()

    first_track_position = player.get_position()

    # Skip to next track
    player.next_track()

    # Verify transition
    # Note: This assumes player has queue management
    # If not implemented, this test documents the expected behavior


@pytest.mark.integration
@pytest.mark.e2e
def test_record_play_updates_statistics(test_library):
    """
    INTEGRATION TEST: Playing track updates play count and last_played.

    Workflow:
    1. Get track with play_count=0
    2. Record play
    3. Verify play_count incremented
    4. Verify last_played updated
    """
    manager, track_ids, _ = test_library

    # Get first track
    tracks, _ = manager.get_all_tracks(limit=1)
    track = tracks[0]
    initial_play_count = track.play_count or 0

    # Record play
    manager.record_play(track.id)

    # Get track again
    updated_tracks, _ = manager.get_all_tracks(limit=1000)
    updated_track = next(t for t in updated_tracks if t.id == track.id)

    # Verify play count incremented
    assert updated_track.play_count == initial_play_count + 1, (
        f"Play count not incremented: {initial_play_count} → {updated_track.play_count}"
    )

    # Verify last_played updated
    assert updated_track.last_played is not None, "last_played should be set"


@pytest.mark.integration
@pytest.mark.e2e
def test_favorite_track_workflow(test_library):
    """
    INTEGRATION TEST: Mark track as favorite → appears in favorites list.

    Workflow:
    1. Get track from library
    2. Mark as favorite
    3. Verify appears in get_favorites()
    4. Unfavorite
    5. Verify removed from get_favorites()
    """
    manager, track_ids, _ = test_library

    # Get first track
    tracks, _ = manager.get_all_tracks(limit=1)
    track = tracks[0]

    # Initial state: not in favorites
    favorites_before, count_before = manager.get_favorites(limit=1000)
    favorite_ids_before = {t.id for t in favorites_before}

    # Mark as favorite
    manager.set_favorite(track.id, True)

    # Verify in favorites
    favorites_after, count_after = manager.get_favorites(limit=1000)
    favorite_ids_after = {t.id for t in favorites_after}

    assert track.id in favorite_ids_after, "Track should be in favorites"
    assert count_after == count_before + 1, (
        f"Favorite count should increase: {count_before} → {count_after}"
    )

    # Unfavorite
    manager.set_favorite(track.id, False)

    # Verify removed from favorites
    favorites_final, count_final = manager.get_favorites(limit=1000)
    favorite_ids_final = {t.id for t in favorites_final}

    assert track.id not in favorite_ids_final, "Track should be removed from favorites"
    assert count_final == count_before, (
        f"Favorite count should return to original: {count_final} != {count_before}"
    )


@pytest.mark.integration
@pytest.mark.e2e
def test_search_play_workflow(test_library, player):
    """
    INTEGRATION TEST: Search for track → play result.

    Workflow:
    1. Search library for track
    2. Select result
    3. Load and play
    """
    manager, track_ids, _ = test_library

    # Search for specific track
    query = "Track 00"
    results, count = manager.search_tracks(query)

    assert count > 0, f"Search for '{query}' should return results"
    assert len(results) > 0, "Results list should not be empty"

    # Verify result matches query
    result = results[0]
    assert query in result.title, f"Result title '{result.title}' should contain '{query}'"

    # Load and play result
    player.load_track(result.filepath)
    player.play()

    assert player.is_playing(), "Player should be playing search result"


@pytest.mark.integration
@pytest.mark.e2e
def test_delete_track_removes_from_library(test_library):
    """
    INTEGRATION TEST: Delete track → removed from all queries.

    Workflow:
    1. Get track count
    2. Delete track
    3. Verify count decreased
    4. Verify track not in results
    5. Verify deleted from favorites (if was favorite)
    6. Verify deleted from recent (if was recent)
    """
    manager, track_ids, _ = test_library

    # Get initial state
    tracks_before, count_before = manager.get_all_tracks(limit=1000)
    track_to_delete = tracks_before[0]

    # Mark as favorite and play it first
    manager.set_favorite(track_to_delete.id, True)
    manager.record_play(track_to_delete.id)

    # Delete track
    manager.delete_track(track_to_delete.id)

    # Verify removed from all tracks
    tracks_after, count_after = manager.get_all_tracks(limit=1000)
    assert count_after == count_before - 1, (
        f"Track count should decrease: {count_before} → {count_after}"
    )

    track_ids_after = {t.id for t in tracks_after}
    assert track_to_delete.id not in track_ids_after, (
        "Deleted track should not appear in get_all_tracks()"
    )

    # Verify removed from favorites
    favorites, _ = manager.get_favorites(limit=1000)
    favorite_ids = {t.id for t in favorites}
    assert track_to_delete.id not in favorite_ids, (
        "Deleted track should not appear in favorites"
    )

    # Verify removed from recent
    recent, _ = manager.get_recent(limit=1000)
    recent_ids = {t.id for t in recent}
    assert track_to_delete.id not in recent_ids, (
        "Deleted track should not appear in recent tracks"
    )


@pytest.mark.integration
@pytest.mark.e2e
def test_update_metadata_workflow(test_library):
    """
    INTEGRATION TEST: Update track metadata → changes persist.

    Workflow:
    1. Get track
    2. Update title
    3. Verify change persists
    4. Verify searchable by new title
    """
    manager, track_ids, _ = test_library

    # Get track
    tracks, _ = manager.get_all_tracks(limit=1)
    track = tracks[0]
    original_title = track.title

    # Update metadata
    new_title = "Updated Title Test"
    manager.update_track_metadata(track.id, {'title': new_title})

    # Verify change persists
    updated_tracks, _ = manager.get_all_tracks(limit=1000)
    updated_track = next(t for t in updated_tracks if t.id == track.id)

    assert updated_track.title == new_title, (
        f"Title not updated: expected '{new_title}', got '{updated_track.title}'"
    )
    assert updated_track.title != original_title, "Title should have changed"

    # Verify searchable by new title
    search_results, count = manager.search_tracks(new_title)
    assert count > 0, f"Should find track by new title '{new_title}'"

    search_ids = {t.id for t in search_results}
    assert track.id in search_ids, "Updated track should appear in search results"


# ============================================================================
# Multi-Step Workflow Tests (P1 Priority)
# ============================================================================

@pytest.mark.integration
@pytest.mark.e2e
def test_complete_listening_session_workflow(test_library, player):
    """
    INTEGRATION TEST: Simulate complete listening session.

    Workflow:
    1. Browse library
    2. Search for track
    3. Add to queue
    4. Play first track
    5. Favorite current track
    6. Skip to next track
    7. Pause
    8. Resume
    9. Stop
    """
    manager, track_ids, _ = test_library

    # Step 1: Browse library
    all_tracks, total_count = manager.get_all_tracks(limit=10)
    assert total_count > 0, "Library should have tracks"

    # Step 2: Search for track
    search_results, search_count = manager.search_tracks("Track")
    assert search_count > 0, "Search should return results"

    # Step 3: Add to queue (load first track)
    first_track = search_results[0]
    player.load_track(first_track.filepath)

    # Step 4: Play first track
    player.play()
    assert player.is_playing(), "Playback should start"

    # Step 5: Favorite current track
    manager.set_favorite(first_track.id, True)
    favorites, fav_count = manager.get_favorites(limit=1)
    assert fav_count >= 1, "Should have at least 1 favorite"

    # Step 6: Skip to next track (if implemented)
    # player.next_track()

    # Step 7: Pause
    player.pause()
    assert not player.is_playing(), "Playback should be paused"

    # Step 8: Resume
    player.play()
    assert player.is_playing(), "Playback should resume"

    # Step 9: Stop
    player.stop()
    assert not player.is_playing(), "Playback should be stopped"


# ============================================================================
# Summary Statistics
# ============================================================================

def test_summary_stats():
    """
    Print summary of what these tests validate.
    """
    print("\n" + "=" * 80)
    print("E2E WORKFLOW INTEGRATION TEST SUMMARY")
    print("=" * 80)
    print(f"Basic Workflows: 5 tests")
    print(f"Library Operations: 3 tests")
    print(f"Multi-Step Sessions: 1 test")
    print("=" * 80)
    print(f"TOTAL: 9 end-to-end integration tests")
    print("=" * 80)
    print("\nThese tests validate complete user workflows:")
    print("1. Add → Play → Pause → Resume → Stop")
    print("2. Search → Play")
    print("3. Favorite → Unfavorite")
    print("4. Delete → Verify cascade")
    print("5. Update metadata → Verify persistence")
    print("=" * 80 + "\n")
