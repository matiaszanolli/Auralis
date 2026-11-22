"""Playlist read-then-write mutations hold the write lock from their first read (#6562).

pysqlite begins a transaction at the first INSERT/UPDATE/DELETE, so remove_track
read the deleted row's position (and reorder_track the whole ordering) outside
any transaction. A second mutation could commit in between and the first then
wrote from a stale snapshot: removing B and C from [A B C D] concurrently left
D at position 2. The tests force exactly that interleaving: the first remover
pauses after its read until the second remover finishes (or 0.5 s pass).
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest
from sqlalchemy import Select, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Track, track_playlist
from auralis.library.repositories.playlist_repository import PlaylistRepository


@pytest.fixture
def playlist():
    db_path = Path(tempfile.mkdtemp()) / "library.db"
    manager = MigrationManager(str(db_path))
    assert manager.migrate_to_latest()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 10})
    factory = sessionmaker(bind=engine)
    with factory() as session:
        for i in range(1, 5):
            session.add(Track(id=i, filepath=f"/tmp/t{i}.flac", title=f"T{i}", duration=60.0,
                              sample_rate=44100, channels=2, format="FLAC"))
        session.commit()
    repo = PlaylistRepository(factory)
    playlist_id = repo.create("Mix").id
    for track_id in (1, 2, 3, 4):  # A=1 B=2 C=3 D=4 at positions 0..3
        assert repo.add_track(playlist_id, track_id)
    yield repo, factory, playlist_id
    engine.dispose()
    manager.close()


def _order(factory, playlist_id):
    with factory() as session:
        return [tuple(row) for row in session.execute(
            select(track_playlist.c.track_id, track_playlist.c.position)
            .where(track_playlist.c.playlist_id == playlist_id)
            .order_by(track_playlist.c.position)
        ).all()]


def _pause_first_reader(monkeypatch, other_done: threading.Event):
    """The first SELECT any thread runs is followed by a wait (<= 0.5 s) for the other mutation."""
    paused = []

    def pausing(real):
        def method(self, statement, *args, **kwargs):
            result = real(self, statement, *args, **kwargs)
            if not paused and isinstance(statement, Select):
                paused.append(threading.current_thread().name)
                other_done.wait(0.5)
            return result
        return method

    monkeypatch.setattr(Session, "scalar", pausing(Session.scalar))
    monkeypatch.setattr(Session, "execute", pausing(Session.execute))


def test_concurrent_removals_of_neighbouring_rows_stay_contiguous(playlist, monkeypatch):
    repo, factory, playlist_id = playlist
    second_done = threading.Event()
    _pause_first_reader(monkeypatch, second_done)

    # C's remover reads position 2 and pauses; B's removal then shifts D down to 2,
    # and a stale C removal would shift only rows past 2, leaving D's gap.
    first = threading.Thread(target=repo.remove_track, args=(playlist_id, 3), name="remove-C")
    first.start()
    threading.Event().wait(0.1)  # let the first remover reach its paused read
    assert repo.remove_track(playlist_id, 2)
    second_done.set()
    first.join(10)

    assert _order(factory, playlist_id) == [(1, 0), (4, 1)]


def test_concurrent_reorders_both_take_effect(playlist, monkeypatch):
    repo, factory, playlist_id = playlist
    second_done = threading.Event()
    _pause_first_reader(monkeypatch, second_done)

    # [A B C D]: move A to the end, and concurrently move B to the end.
    first = threading.Thread(target=repo.reorder_track, args=(playlist_id, 0, 3), name="move-A")
    first.start()
    threading.Event().wait(0.1)
    assert repo.reorder_track(playlist_id, 0, 3)
    second_done.set()
    first.join(10)

    order = [track_id for track_id, _ in _order(factory, playlist_id)]
    # Serialised: the first move gives [B C D A]; the second then moves B -> [C D A B].
    assert order == [3, 4, 1, 2]
    assert [pos for _, pos in _order(factory, playlist_id)] == [0, 1, 2, 3]
