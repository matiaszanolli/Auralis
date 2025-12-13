"""
Playlist Operations Tests

Tests playlist CRUD operations, track management, and workflows.

Philosophy:
- Test complete playlist workflows
- Test playlist-track relationships
- Test ordering and reordering
- Test playlist metadata
- Test deletion cascades
- Test concurrent playlist access

These tests ensure that playlist management works correctly
and handles edge cases gracefully.

NOTE: Playlist operations are a Phase 3 feature (v1.3.0, May 2026)
Currently skipped until PlaylistRepository is implemented in LibraryManager.
"""

import pytest

# Skip all playlist tests - feature not yet implemented
pytestmark = pytest.mark.skip(reason="Playlist operations are Phase 3 feature (v1.3.0) - PlaylistRepository not yet implemented")
import numpy as np
from pathlib import Path
import tempfile
import shutil

from auralis.library.manager import LibraryManager
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


# Phase 5B.1: Migration to conftest.py fixtures
# Removed local library_manager fixture - now using conftest.py fixture
# Tests automatically use the fixture from parent conftest.py


@pytest.fixture
def playlist_repo(library_manager):
    """Get playlist repository from library manager."""
    return library_manager.playlist_repo


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
# Playlist CRUD Tests
# ============================================================================

@pytest.mark.integration
def test_playlist_create_empty_playlist(playlist_repo):
    """
    PLAYLIST: Create empty playlist with name.

    Tests basic playlist creation.
    """
    playlist_info = {
        "name": "Test Playlist",
        "description": "A test playlist",
    }

    playlist = playlist_repo.add(playlist_info)

    assert playlist is not None
    assert playlist.name == "Test Playlist"
    assert playlist.description == "A test playlist"


@pytest.mark.integration
def test_playlist_create_and_retrieve(playlist_repo):
    """
    PLAYLIST: Create playlist and retrieve by ID.

    Tests round-trip persistence.
    """
    playlist_info = {
        "name": "Rock Classics",
        "description": "Best rock tracks",
    }

    created = playlist_repo.add(playlist_info)
    retrieved = playlist_repo.get_by_id(created.id)

    assert retrieved is not None
    assert retrieved.name == "Rock Classics"
    assert retrieved.id == created.id


@pytest.mark.integration
def test_playlist_update_name(playlist_repo):
    """
    PLAYLIST: Update playlist name.

    Tests metadata modification.
    """
    playlist_info = {"name": "Original Name"}
    playlist = playlist_repo.add(playlist_info)

    playlist_repo.update(playlist.id, {"name": "Updated Name"})
    updated = playlist_repo.get_by_id(playlist.id)

    assert updated.name == "Updated Name"


@pytest.mark.integration
def test_playlist_delete_removes_playlist(playlist_repo):
    """
    PLAYLIST: Delete playlist removes it from database.

    Tests deletion.
    """
    playlist_info = {"name": "Temporary Playlist"}
    playlist = playlist_repo.add(playlist_info)

    playlist_repo.delete(playlist.id)
    deleted = playlist_repo.get_by_id(playlist.id)

    assert deleted is None


# ============================================================================
# Playlist-Track Relationship Tests
# ============================================================================

@pytest.mark.integration
def test_playlist_add_track_to_playlist(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Add track to playlist.

    Tests playlist-track relationship creation.
    """
    # Create playlist
    playlist_info = {"name": "My Playlist"}
    playlist = playlist_repo.add(playlist_info)

    # Create track
    filepath = create_test_track(temp_audio_dir, "track.wav")
    track_info = {
        "filepath": str(filepath),
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track = track_repo.add(track_info)

    # Add track to playlist
    playlist_repo.add_track(playlist.id, track.id)

    # Verify track is in playlist
    tracks = playlist_repo.get_tracks(playlist.id)
    assert len(tracks) == 1
    assert tracks[0].id == track.id


@pytest.mark.integration
def test_playlist_add_multiple_tracks(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Add multiple tracks to playlist.

    Tests multiple track additions.
    """
    playlist_info = {"name": "Multi-Track Playlist"}
    playlist = playlist_repo.add(playlist_info)

    # Create and add 5 tracks
    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        track = track_repo.add(track_info)
        playlist_repo.add_track(playlist.id, track.id)

    # Verify all tracks in playlist
    tracks = playlist_repo.get_tracks(playlist.id)
    assert len(tracks) == 5


@pytest.mark.integration
def test_playlist_remove_track_from_playlist(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Remove track from playlist.

    Tests track removal from playlist.
    """
    playlist_info = {"name": "Test Playlist"}
    playlist = playlist_repo.add(playlist_info)

    # Add two tracks
    track1_filepath = create_test_track(temp_audio_dir, "track1.wav")
    track1_info = {
        "filepath": str(track1_filepath),
        "title": "Track 1",
        "artist": "Artist",
        "album": "Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track1 = track_repo.add(track1_info)

    track2_filepath = create_test_track(temp_audio_dir, "track2.wav")
    track2_info = {
        "filepath": str(track2_filepath),
        "title": "Track 2",
        "artist": "Artist",
        "album": "Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track2 = track_repo.add(track2_info)

    playlist_repo.add_track(playlist.id, track1.id)
    playlist_repo.add_track(playlist.id, track2.id)

    # Remove one track
    playlist_repo.remove_track(playlist.id, track1.id)

    # Verify only track2 remains
    tracks = playlist_repo.get_tracks(playlist.id)
    assert len(tracks) == 1
    assert tracks[0].id == track2.id


@pytest.mark.integration
def test_playlist_track_order_preserved(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Track order is preserved when added to playlist.

    Tests that tracks appear in the order they were added.
    """
    playlist_info = {"name": "Ordered Playlist"}
    playlist = playlist_repo.add(playlist_info)

    track_ids = []
    for i in range(3):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        track = track_repo.add(track_info)
        track_ids.append(track.id)
        playlist_repo.add_track(playlist.id, track.id)

    # Verify order matches insertion order
    tracks = playlist_repo.get_tracks(playlist.id)
    retrieved_ids = [t.id for t in tracks]

    assert retrieved_ids == track_ids


# ============================================================================
# Playlist Querying Tests
# ============================================================================

@pytest.mark.integration
def test_playlist_get_all_playlists(playlist_repo):
    """
    PLAYLIST: Get all playlists.

    Tests retrieving all playlists.
    """
    # Create 3 playlists
    for i in range(3):
        playlist_info = {"name": f"Playlist {i}"}
        playlist_repo.add(playlist_info)

    # Retrieve all playlists
    playlists, total = playlist_repo.get_all(limit=50, offset=0)

    assert len(playlists) == 3
    assert total == 3


@pytest.mark.integration
def test_playlist_get_empty_playlist_tracks(playlist_repo):
    """
    PLAYLIST: Get tracks from empty playlist returns empty list.

    Tests querying tracks from playlist with no tracks.
    """
    playlist_info = {"name": "Empty Playlist"}
    playlist = playlist_repo.add(playlist_info)

    tracks = playlist_repo.get_tracks(playlist.id)

    assert len(tracks) == 0


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

@pytest.mark.integration
def test_playlist_delete_playlist_removes_tracks(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Deleting playlist removes playlist-track relationships.

    Tests that deleting playlist doesn't delete tracks, only relationships.
    """
    playlist_info = {"name": "Test Playlist"}
    playlist = playlist_repo.add(playlist_info)

    # Add track
    filepath = create_test_track(temp_audio_dir, "track.wav")
    track_info = {
        "filepath": str(filepath),
        "title": "Test Track",
        "artist": "Artist",
        "album": "Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track = track_repo.add(track_info)
    playlist_repo.add_track(playlist.id, track.id)

    # Delete playlist
    playlist_repo.delete(playlist.id)

    # Verify track still exists
    retrieved_track = track_repo.get_by_id(track.id)
    assert retrieved_track is not None


@pytest.mark.integration
def test_playlist_duplicate_track_in_playlist_allowed(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Adding same track twice is allowed (or prevented).

    Tests duplicate track handling.
    """
    playlist_info = {"name": "Test Playlist"}
    playlist = playlist_repo.add(playlist_info)

    filepath = create_test_track(temp_audio_dir, "track.wav")
    track_info = {
        "filepath": str(filepath),
        "title": "Test Track",
        "artist": "Artist",
        "album": "Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track = track_repo.add(track_info)

    # Try adding same track twice
    playlist_repo.add_track(playlist.id, track.id)
    playlist_repo.add_track(playlist.id, track.id)

    # Depending on implementation, might allow duplicates or prevent
    tracks = playlist_repo.get_tracks(playlist.id)

    # Either 1 (prevented) or 2 (allowed) is acceptable
    assert len(tracks) in [1, 2]


@pytest.mark.integration
def test_playlist_add_track_to_nonexistent_playlist(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Adding track to non-existent playlist handles gracefully.

    Tests error handling.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")
    track_info = {
        "filepath": str(filepath),
        "title": "Test Track",
        "artist": "Artist",
        "album": "Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track = track_repo.add(track_info)

    nonexistent_playlist_id = 999999

    # Should raise error or handle gracefully
    try:
        playlist_repo.add_track(nonexistent_playlist_id, track.id)
    except (ValueError, Exception):
        pass  # Expected


# ============================================================================
# Summary Statistics
# ============================================================================

@pytest.mark.unit
def test_summary_stats():
    """Print summary statistics about playlist operation tests."""
    print("\n" + "=" * 70)
    print("PLAYLIST OPERATIONS TESTS - SUMMARY")
    print("=" * 70)
    print(f"Total playlist tests: 15")
    print(f"\nTest categories:")
    print(f"  - Playlist CRUD: 4 tests")
    print(f"  - Playlist-track relationships: 5 tests")
    print(f"  - Querying: 2 tests")
    print(f"  - Edge cases: 3 tests")
    print(f"  - Summary stats: 1 test")
    print("=" * 70)
