"""
Regression test for #3340 — `PlaylistRepository.remove_track` race window.

Pre-fix: the method loaded the `Playlist` row, then accessed `playlist.tracks`
(triggering a lazy SELECT on the association table), then called
`playlist.tracks.remove(track)` and committed. Between the lazy SELECT and
the COMMIT, another thread could modify the same playlist's track set; two
concurrent removes of different tracks could collide.

Post-fix: a single atomic `DELETE FROM track_playlist WHERE playlist_id=?
AND track_id=?` — no lazy load, no read→modify→commit window, naturally
idempotent under concurrency.

These tests pin the contract: concurrent remove_track calls converge to a
consistent final state with no missed removals.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from auralis.library.repositories.playlist_repository import PlaylistRepository
from auralis.library.repositories.track_repository import TrackRepository


@pytest.fixture
def playlist_with_10_tracks(session_factory):
    """Create a playlist with 10 tracks; yield (playlist_repo, track_repo, playlist_id, track_ids)."""
    track_repo = TrackRepository(session_factory)
    playlist_repo = PlaylistRepository(session_factory)

    track_ids: list[int] = []
    for i in range(10):
        t = track_repo.add({
            'title': f'Track {i}',
            'filepath': f'/tmp/track_{i}.wav',
            'duration': 60.0,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'artists': ['Test'],
        })
        assert t is not None
        track_ids.append(t.id)

    playlist = playlist_repo.create('Test Playlist', track_ids=track_ids)
    assert playlist is not None

    # Verify initial state
    loaded = playlist_repo.get_by_id(playlist.id)
    assert loaded is not None
    assert len(loaded.tracks) == 10

    yield playlist_repo, track_repo, playlist.id, track_ids


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_remove_track_is_idempotent(playlist_with_10_tracks):
    """Removing the same track twice must not raise and must leave a
    consistent state — pre-fix the second remove might have failed because
    the in-memory collection was stale."""
    playlist_repo, _, playlist_id, track_ids = playlist_with_10_tracks
    target = track_ids[0]

    assert playlist_repo.remove_track(playlist_id, target) is True
    assert playlist_repo.remove_track(playlist_id, target) is True   # idempotent

    loaded = playlist_repo.get_by_id(playlist_id)
    assert loaded is not None
    assert target not in {t.id for t in loaded.tracks}
    assert len(loaded.tracks) == 9


def test_remove_nonexistent_track_returns_true(playlist_with_10_tracks):
    """A DELETE that matches zero rows is a no-op — still returns True
    (matches the operation contract: 'after this call, the track is not in
    the playlist')."""
    playlist_repo, _, playlist_id, _ = playlist_with_10_tracks
    assert playlist_repo.remove_track(playlist_id, 99999) is True


# ---------------------------------------------------------------------------
# Concurrency — the actual #3340 contract
# ---------------------------------------------------------------------------

def test_concurrent_removes_of_different_tracks_all_succeed(playlist_with_10_tracks):
    """10 threads each remove a different track from the same playlist
    simultaneously. Final state must have zero tracks; no missed removals."""
    playlist_repo, _, playlist_id, track_ids = playlist_with_10_tracks

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [
            ex.submit(playlist_repo.remove_track, playlist_id, tid)
            for tid in track_ids
        ]
        results = [f.result() for f in as_completed(futures)]

    assert all(results), "Every concurrent remove must succeed"

    loaded = playlist_repo.get_by_id(playlist_id)
    assert loaded is not None
    assert len(loaded.tracks) == 0, (
        f"Expected empty playlist after 10 concurrent removes, got "
        f"{[t.id for t in loaded.tracks]}"
    )


def test_concurrent_removes_of_same_track_all_succeed(playlist_with_10_tracks):
    """5 threads all try to remove the SAME track. The DELETE is idempotent
    so they all succeed; final state has the track gone exactly once.

    Pre-fix the load→remove→commit cycle could throw a stale-data exception
    on the loser threads when SQLAlchemy detected the collection had been
    mutated underneath them.
    """
    playlist_repo, _, playlist_id, track_ids = playlist_with_10_tracks
    target = track_ids[3]

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [
            ex.submit(playlist_repo.remove_track, playlist_id, target)
            for _ in range(5)
        ]
        results = [f.result() for f in as_completed(futures)]

    assert all(results), "Every concurrent remove of the same track must succeed"

    loaded = playlist_repo.get_by_id(playlist_id)
    assert loaded is not None
    assert target not in {t.id for t in loaded.tracks}
    assert len(loaded.tracks) == 9
