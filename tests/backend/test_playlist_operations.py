"""
Playlist Operations Tests

Tests playlist CRUD operations, track management, and workflows against a
real temp-DB `PlaylistRepository` (#4381).

Philosophy:
- Test complete playlist workflows
- Test playlist-track relationships
- Test ordering and reordering
- Test playlist metadata
- Test deletion cascades
- Test concurrent playlist access

These tests ensure that playlist management works correctly
and handles edge cases gracefully.

Sibling of test_playlist_integration.py (#4691, already repo-backed): that
file drives the same CRUD/track-membership surface through one large
`library_with_playlists` fixture; this file uses per-test fixtures
(`playlist_repo`/`track_repo`) for finer-grained isolation and covers a few
scenarios integration.py doesn't (empty-playlist tracks, add-to-nonexistent-
playlist, multi-track add).
"""

import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

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
# Removed local library_database fixture - now using conftest.py fixture
# Tests automatically use the fixture from parent conftest.py


@pytest.fixture
def playlist_repo(library_database):
    """Get playlist repository from library manager.

    #4381: LibraryDatabase's convenience accessor is `.playlists`, not the
    `.playlist_repo` this fixture used to reach for (which never existed —
    every test ERRORed in fixture setup).
    """
    return library_database.playlists


@pytest.fixture
def track_repo(library_database):
    """Get track repository from library manager."""
    return library_database.tracks


def create_test_track(directory: Path, filename: str):
    """Create a minimal test audio file."""
    audio = np.random.randn(44100, 2) * 0.5
    filepath = directory / filename
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')
    return filepath


def _track_info(filepath: Path, title: str) -> dict:
    """Standard track_info dict for TrackRepository.add() (#4381).

    `artists` must be a list — TrackRepository.add() reads
    `track_info.get('artists', [])`; a singular `artist` key is silently
    ignored rather than erroring, which is exactly the kind of stale-API
    drift this file was already carrying.
    """
    return {
        "filepath": str(filepath),
        "title": title,
        "artists": ["Test Artist"],
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }


# ============================================================================
# Playlist CRUD Tests
# ============================================================================

@pytest.mark.integration
def test_playlist_create_empty_playlist(playlist_repo):
    """
    PLAYLIST: Create empty playlist with name.

    Tests basic playlist creation.
    """
    playlist = playlist_repo.create(name="Test Playlist", description="A test playlist")

    assert playlist is not None
    assert playlist.name == "Test Playlist"
    assert playlist.description == "A test playlist"


@pytest.mark.integration
def test_playlist_create_and_retrieve(playlist_repo):
    """
    PLAYLIST: Create playlist and retrieve by ID.

    Tests round-trip persistence.
    """
    created = playlist_repo.create(name="Rock Classics", description="Best rock tracks")
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
    playlist = playlist_repo.create(name="Original Name")

    playlist_repo.update(playlist.id, {"name": "Updated Name"})
    updated = playlist_repo.get_by_id(playlist.id)

    assert updated.name == "Updated Name"


@pytest.mark.integration
def test_playlist_delete_removes_playlist(playlist_repo):
    """
    PLAYLIST: Delete playlist removes it from database.

    Tests deletion.
    """
    playlist = playlist_repo.create(name="Temporary Playlist")

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
    playlist = playlist_repo.create(name="My Playlist")

    filepath = create_test_track(temp_audio_dir, "track.wav")
    track = track_repo.add(_track_info(filepath, "Test Track"))

    playlist_repo.add_track(playlist.id, track.id)

    tracks = playlist_repo.get_by_id(playlist.id).tracks
    assert len(tracks) == 1
    assert tracks[0].id == track.id


@pytest.mark.integration
def test_playlist_add_multiple_tracks(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Add multiple tracks to playlist.

    Tests multiple track additions.
    """
    playlist = playlist_repo.create(name="Multi-Track Playlist")

    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")
        track = track_repo.add(_track_info(filepath, f"Track {i}"))
        playlist_repo.add_track(playlist.id, track.id)

    tracks = playlist_repo.get_by_id(playlist.id).tracks
    assert len(tracks) == 5


@pytest.mark.integration
def test_playlist_remove_track_from_playlist(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Remove track from playlist.

    Tests track removal from playlist.
    """
    playlist = playlist_repo.create(name="Test Playlist")

    track1 = track_repo.add(_track_info(create_test_track(temp_audio_dir, "track1.wav"), "Track 1"))
    track2 = track_repo.add(_track_info(create_test_track(temp_audio_dir, "track2.wav"), "Track 2"))

    playlist_repo.add_track(playlist.id, track1.id)
    playlist_repo.add_track(playlist.id, track2.id)

    playlist_repo.remove_track(playlist.id, track1.id)

    tracks = playlist_repo.get_by_id(playlist.id).tracks
    assert len(tracks) == 1
    assert tracks[0].id == track2.id


@pytest.mark.integration
def test_playlist_track_order_preserved(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Track order is preserved when added to playlist.

    Tests that tracks appear in the order they were added.
    """
    playlist = playlist_repo.create(name="Ordered Playlist")

    track_ids = []
    for i in range(3):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")
        track = track_repo.add(_track_info(filepath, f"Track {i}"))
        track_ids.append(track.id)
        playlist_repo.add_track(playlist.id, track.id)

    tracks = playlist_repo.get_by_id(playlist.id).tracks
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
    for i in range(3):
        playlist_repo.create(name=f"Playlist {i}")

    playlists, total = playlist_repo.get_all(limit=50, offset=0)

    assert len(playlists) == 3
    assert total == 3


@pytest.mark.integration
def test_playlist_get_empty_playlist_tracks(playlist_repo):
    """
    PLAYLIST: Get tracks from empty playlist returns empty list.

    Tests querying tracks from playlist with no tracks.
    """
    playlist = playlist_repo.create(name="Empty Playlist")

    tracks = playlist_repo.get_by_id(playlist.id).tracks

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
    playlist = playlist_repo.create(name="Test Playlist")

    filepath = create_test_track(temp_audio_dir, "track.wav")
    track = track_repo.add(_track_info(filepath, "Test Track"))
    playlist_repo.add_track(playlist.id, track.id)

    playlist_repo.delete(playlist.id)

    # Deleting the playlist must not cascade to the track itself.
    retrieved_track = track_repo.get_by_id(track.id)
    assert retrieved_track is not None


@pytest.mark.integration
def test_playlist_duplicate_track_in_playlist_allowed(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Adding the same track twice is idempotent.

    add_track's composite-PK INSERT OR IGNORE (see
    playlist_membership_mixin.py) makes a second add_track for a track
    already in the playlist a no-op — it returns True but does not
    duplicate the row.
    """
    playlist = playlist_repo.create(name="Test Playlist")

    filepath = create_test_track(temp_audio_dir, "track.wav")
    track = track_repo.add(_track_info(filepath, "Test Track"))

    assert playlist_repo.add_track(playlist.id, track.id) is True
    assert playlist_repo.add_track(playlist.id, track.id) is True

    tracks = playlist_repo.get_by_id(playlist.id).tracks
    assert len(tracks) == 1


@pytest.mark.integration
def test_playlist_add_track_to_nonexistent_playlist(temp_audio_dir, playlist_repo, track_repo):
    """
    PLAYLIST: Adding a track to a non-existent playlist is a no-op, not an
    exception — add_track's existence check returns False on lookup miss
    (see playlist_membership_mixin.py) rather than raising.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")
    track = track_repo.add(_track_info(filepath, "Test Track"))

    nonexistent_playlist_id = 999999

    result = playlist_repo.add_track(nonexistent_playlist_id, track.id)

    assert result is False
