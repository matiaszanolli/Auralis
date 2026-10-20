"""Regression tests: playlist positions stay contiguous (#5573)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

add_track(position=...) used to insert without shifting later rows
(duplicate positions, undefined order), repositioning left gaps, and
library-track deletion removed association rows without compacting —
which together made reorder_track's `position == from_index` lookups
miss and playlists un-reorderable. All three writers now keep positions
contiguous 0..N-1, and reorder_track resolves rows by logical index so
legacy gaps can't wedge it.

Real tmp-file DB at the current schema version.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from auralis.__version__ import __db_schema_version__
from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Track
from auralis.library.repositories.playlist_repository import PlaylistRepository
from auralis.library.repositories.track_repository import TrackRepository


@pytest.fixture
def repos():
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "library.db"
    manager = MigrationManager(str(db_path))
    assert manager.migrate_to_latest()
    assert manager.get_current_version() == __db_schema_version__

    engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
    session_factory = sessionmaker(bind=engine)
    playlists = PlaylistRepository(session_factory)
    tracks = TrackRepository(session_factory)

    with session_factory() as session:
        for i in range(1, 6):
            session.add(Track(
                id=i,
                filepath=f"/tmp/track_{i}.flac",
                title=f"Track {i}",
                duration=60.0 + i,
                sample_rate=44100,
                channels=2,
                format="FLAC",
            ))
        session.commit()

    playlist = playlists.create("Mix")
    playlist_id = playlist.id
    for tid in (1, 2, 3):
        playlists.add_track(playlist_id, tid)

    yield playlists, tracks, session_factory, playlist_id

    engine.dispose()
    manager.close()


def _positions(repos, session_factory, playlist_id) -> list[tuple[int, int]]:
    from auralis.library.models import track_playlist
    with session_factory() as session:
        rows = session.execute(
            select(track_playlist.c.track_id, track_playlist.c.position)
            .where(track_playlist.c.playlist_id == playlist_id)
            .order_by(track_playlist.c.position)
        ).all()
    return [(int(tid), int(pos)) for tid, pos in rows]


class TestPositionalInsert:
    def test_insert_at_position_shifts_later_rows(self, repos):
        playlists, _, sf, pid = repos
        # [1,2,3], insert track 4 at position 1 → [1,4,2,3]
        assert playlists.add_track(pid, 4, position=1) is True

        rows = _positions(playlists, sf, pid)
        assert rows == [(1, 0), (4, 1), (2, 2), (3, 3)]

    def test_reposition_of_present_track_shifts_rows(self, repos):
        playlists, _, sf, pid = repos
        # Move track 1 (position 0) to position 2.
        assert playlists.add_track(pid, 1, position=2) is True

        rows = _positions(playlists, sf, pid)
        assert rows == [(2, 0), (3, 1), (1, 2)]

    def test_out_of_range_position_appends_without_a_gap(self, repos):
        playlists, _, sf, pid = repos
        assert playlists.add_track(pid, 4, position=99) is True

        rows = _positions(playlists, sf, pid)
        assert rows == [(1, 0), (2, 1), (3, 2), (4, 3)]


class TestReorderTolerance:
    def test_move_c_to_front_via_positional_insert(self, repos):
        """The issue's repro: [A0,B1,C2], move C to position 0 via
        add_track(position=0) — used to produce [(A,0),(C,0),(B,1)]."""
        playlists, _, sf, pid = repos
        assert playlists.add_track(pid, 3, position=0) is True

        rows = _positions(playlists, sf, pid)
        assert rows == [(3, 0), (1, 1), (2, 2)]

        # And the playlist must remain reorderable afterwards.
        assert playlists.reorder_track(pid, 2, 0) is True
        assert _positions(playlists, sf, pid)[0] == (2, 0)

    def test_reorder_track_on_a_legacy_gapped_playlist(self, repos):
        """Simulate a legacy gapped playlist [(1,0),(3,2)]: reorder must
        resolve rows by logical index and heal the gap."""
        playlists, _, sf, pid = repos
        playlists.remove_track(pid, 3)  # [1,2]; then force a gap by hand

        from sqlalchemy import update as sa_update, and_
        from auralis.library.models import track_playlist
        with sf() as session:
            session.execute(
                sa_update(track_playlist)
                .where(track_playlist.c.playlist_id == pid)
                .where(track_playlist.c.track_id == 2)
                .values(position=5)
            )
            session.commit()

        # from_index=1 (logical: track 2 sits at logical index 1) → to 0.
        assert playlists.reorder_track(pid, 1, 0) is True
        rows = _positions(playlists, sf, pid)
        assert rows == [(2, 0), (1, 1)]


class TestDeleteCompaction:
    def test_library_delete_compacts_positions_and_keeps_reorder_working(self, repos):
        """The issue's repro: delete B (track 2) from [A0,B1,C2] left
        [(A,0),(C,2)] and reorder_track(1, 0) returned False."""
        playlists, tracks, sf, pid = repos
        assert tracks.delete(2) is True

        rows = _positions(playlists, sf, pid)
        assert rows == [(1, 0), (3, 1)], "positions not compacted after delete"

        assert playlists.reorder_track(pid, 1, 0) is True
        assert _positions(playlists, sf, pid) == [(3, 0), (1, 1)]
