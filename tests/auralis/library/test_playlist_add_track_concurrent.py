"""
Regression test for #3724 + #3725 — concurrent ``add_track`` races.

Pre-fix (schema v015 and below): ``track_playlist`` had no PK or unique
constraint and ``add_track`` defended against duplicates via SELECT EXISTS
then ``playlist.tracks.append(track)``. Two concurrent
``POST /playlists/{id}/tracks`` for the same ``(playlist_id, track_id)``
both passed the EXISTS check and both INSERTed silently — no
IntegrityError fired, duplicates accumulated invisibly.

Post-fix (schema v016 + this PR):
  - Composite PK ``(track_id, playlist_id)`` collapses the duplicate
    race at the DB level: ``INSERT OR IGNORE`` lets at most one
    concurrent caller win.
  - Explicit ``position`` column with ``SELECT MAX(position)+1`` inside
    the same transaction gives concurrent appends distinct, contiguous
    positions instead of racing on the implicit secondary-table order.
  - ``remove_track`` compacts trailing positions so the per-playlist
    invariant ``positions are contiguous 0..N-1`` holds.

These tests pin the new contract.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import select

from auralis.library.models.base import track_playlist
from auralis.library.repositories.playlist_repository import PlaylistRepository
from auralis.library.repositories.track_repository import TrackRepository


@pytest.fixture
def playlist_with_5_tracks(session_factory):
    """Yield (playlist_repo, track_repo, playlist_id, [track_ids])."""
    track_repo = TrackRepository(session_factory)
    playlist_repo = PlaylistRepository(session_factory)

    track_ids: list[int] = []
    for i in range(5):
        t = track_repo.add({
            'title': f'Track {i}',
            'filepath': f'/tmp/concur_add_track_{i}.wav',
            'duration': 60.0,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'artists': ['Test'],
        })
        assert t is not None
        track_ids.append(t.id)

    playlist = playlist_repo.create('Test Playlist', track_ids=[])
    assert playlist is not None
    return playlist_repo, track_repo, playlist.id, track_ids


def _positions_for_playlist(session_factory, playlist_id: int) -> list[tuple[int, int]]:
    """Return [(track_id, position), ...] for a playlist in position order."""
    session = session_factory()
    try:
        rows = session.execute(
            select(track_playlist.c.track_id, track_playlist.c.position)
            .where(track_playlist.c.playlist_id == playlist_id)
            .order_by(track_playlist.c.position)
        ).all()
        return [(r.track_id, r.position) for r in rows]
    finally:
        session.close()


class TestAddTrackConcurrent:
    """#3724: composite PK + INSERT OR IGNORE eliminates duplicate rows."""

    def test_concurrent_add_same_track_produces_one_row(self, session_factory, playlist_with_5_tracks):
        """20 concurrent add_track calls for the same (playlist, track) must
        collapse to a single row in the association table."""
        playlist_repo, _track_repo, playlist_id, track_ids = playlist_with_5_tracks
        target_track = track_ids[0]

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(playlist_repo.add_track, playlist_id, target_track)
                for _ in range(20)
            ]
            results = [f.result() for f in as_completed(futures)]

        # All callers should report success — the unique constraint guarantees
        # the row exists after each call returns even if their own INSERT was
        # ignored.
        assert all(results)

        # Direct DB check: exactly one row in the association table.
        rows = _positions_for_playlist(session_factory, playlist_id)
        track_ids_in_playlist = [tid for tid, _pos in rows]
        assert track_ids_in_playlist.count(target_track) == 1, (
            f"Expected 1 row for track {target_track}, got "
            f"{track_ids_in_playlist.count(target_track)} ({rows})"
        )


class TestAddTrackPositionContract:
    """#3725: position column is contiguous 0..N-1 under concurrent + sequential ADDs."""

    def test_sequential_appends_assign_contiguous_positions(
        self, session_factory, playlist_with_5_tracks
    ):
        playlist_repo, _, playlist_id, track_ids = playlist_with_5_tracks
        for tid in track_ids:
            assert playlist_repo.add_track(playlist_id, tid)

        rows = _positions_for_playlist(session_factory, playlist_id)
        positions = [pos for _tid, pos in rows]
        assert positions == [0, 1, 2, 3, 4]
        # Insertion order preserved.
        assert [tid for tid, _ in rows] == track_ids

    def test_concurrent_appends_get_distinct_positions(
        self, session_factory, playlist_with_5_tracks
    ):
        """Concurrent appends of 5 different tracks must end up at 5
        distinct positions (no two callers grab the same MAX+1)."""
        playlist_repo, _, playlist_id, track_ids = playlist_with_5_tracks

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(playlist_repo.add_track, playlist_id, tid)
                for tid in track_ids
            ]
            assert all(f.result() for f in as_completed(futures))

        rows = _positions_for_playlist(session_factory, playlist_id)
        positions = sorted(pos for _tid, pos in rows)
        # No duplicate positions, contiguous from 0.
        assert positions == [0, 1, 2, 3, 4], f"Got positions {positions}"
        # Every requested track is present exactly once.
        assert sorted(tid for tid, _ in rows) == sorted(track_ids)


class TestRemoveTrackCompactsPositions:
    """#3725: remove_track keeps positions contiguous so reorder_track stays valid."""

    def test_remove_middle_compacts_trailing_positions(
        self, session_factory, playlist_with_5_tracks
    ):
        playlist_repo, _, playlist_id, track_ids = playlist_with_5_tracks
        for tid in track_ids:
            playlist_repo.add_track(playlist_id, tid)

        # Sanity baseline.
        baseline = _positions_for_playlist(session_factory, playlist_id)
        assert [pos for _, pos in baseline] == [0, 1, 2, 3, 4]

        # Remove the middle entry.
        assert playlist_repo.remove_track(playlist_id, track_ids[2])

        after = _positions_for_playlist(session_factory, playlist_id)
        positions = [pos for _, pos in after]
        # Contiguous after compaction.
        assert positions == [0, 1, 2, 3]
        # Order of surviving tracks preserved.
        assert [tid for tid, _ in after] == [
            track_ids[0], track_ids[1], track_ids[3], track_ids[4]
        ]


class TestReorderTrackUsesPositionColumn:
    """#3725: reorder_track operates on the explicit position column."""

    def test_reorder_forward(self, session_factory, playlist_with_5_tracks):
        playlist_repo, _, playlist_id, track_ids = playlist_with_5_tracks
        for tid in track_ids:
            playlist_repo.add_track(playlist_id, tid)

        # Move position 1 → position 3.
        assert playlist_repo.reorder_track(playlist_id, 1, 3)

        rows = _positions_for_playlist(session_factory, playlist_id)
        # Original: [0, 1, 2, 3, 4] → after move(1→3): [0, 2, 3, 1, 4]
        # i.e. track at original-index-1 now sits at position 3.
        ordered = [tid for tid, _ in rows]
        expected = [track_ids[0], track_ids[2], track_ids[3], track_ids[1], track_ids[4]]
        assert ordered == expected, f"Got {ordered}, expected {expected}"

        # Positions still contiguous 0..4.
        positions = [pos for _, pos in rows]
        assert positions == [0, 1, 2, 3, 4]

    def test_reorder_backward(self, session_factory, playlist_with_5_tracks):
        playlist_repo, _, playlist_id, track_ids = playlist_with_5_tracks
        for tid in track_ids:
            playlist_repo.add_track(playlist_id, tid)

        # Move position 3 → position 0.
        assert playlist_repo.reorder_track(playlist_id, 3, 0)

        rows = _positions_for_playlist(session_factory, playlist_id)
        ordered = [tid for tid, _ in rows]
        expected = [track_ids[3], track_ids[0], track_ids[1], track_ids[2], track_ids[4]]
        assert ordered == expected, f"Got {ordered}, expected {expected}"

    def test_reorder_noop_same_position(self, session_factory, playlist_with_5_tracks):
        playlist_repo, _, playlist_id, track_ids = playlist_with_5_tracks
        for tid in track_ids:
            playlist_repo.add_track(playlist_id, tid)

        before = _positions_for_playlist(session_factory, playlist_id)
        assert playlist_repo.reorder_track(playlist_id, 2, 2)
        after = _positions_for_playlist(session_factory, playlist_id)
        assert before == after

    def test_reorder_invalid_indices_returns_false(self, session_factory, playlist_with_5_tracks):
        playlist_repo, _, playlist_id, track_ids = playlist_with_5_tracks
        for tid in track_ids:
            playlist_repo.add_track(playlist_id, tid)

        assert not playlist_repo.reorder_track(playlist_id, 99, 0)
        assert not playlist_repo.reorder_track(playlist_id, 0, 99)
