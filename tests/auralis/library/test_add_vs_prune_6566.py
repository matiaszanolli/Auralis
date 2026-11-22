"""add() racing a delete that prunes the same artist/album keeps the track (#6566).

add() used to SELECT an existing artist/album outside any transaction and insert
the track rows later. A concurrent delete of that artist's last track pruned the
artist (#5596) in between, so the insert hit a foreign-key error and the valid
file came back as a failed add (None). add() now takes the write lock before
its lookups (#6562/#6564), so the delete waits and its prune sees the new track.
The test forces the interleaving: the add pauses right after its artist lookup
until the delete finishes (or 0.5 s pass).
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest
from sqlalchemy import Select, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Album, Artist
from auralis.library.repositories.track_repository import TrackRepository


@pytest.fixture
def tracks():
    db_path = Path(tempfile.mkdtemp()) / "library.db"
    manager = MigrationManager(str(db_path))
    assert manager.migrate_to_latest()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 10})

    @event.listens_for(engine, "connect")
    def _foreign_keys_on(dbapi_connection, _record):  # production enforces them (database_engine.py)
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(bind=engine)
    yield TrackRepository(factory), factory
    engine.dispose()
    manager.close()


def _info(path, title):
    return {"filepath": path, "title": title, "artists": ["Solo"], "album": "Only", "duration": 60.0,
            "sample_rate": 44100, "channels": 2, "format": "FLAC"}


def test_add_survives_a_concurrent_prune_of_its_artist(tracks, monkeypatch):
    repo, factory = tracks
    existing = repo.add(_info("/music/one.flac", "One"))
    assert existing is not None

    delete_done = threading.Event()
    paused = []
    real_execute = Session.execute

    def execute(self, statement, *args, **kwargs):
        result = real_execute(self, statement, *args, **kwargs)
        if (not paused and isinstance(statement, Select)
                and any(d.get("entity") is Artist for d in statement.column_descriptions)):
            paused.append(threading.current_thread().name)
            delete_done.wait(0.5)
        return result

    monkeypatch.setattr(Session, "execute", execute)

    added = []
    adder = threading.Thread(target=lambda: added.append(repo.add(_info("/music/two.flac", "Two"))))
    adder.start()
    threading.Event().wait(0.1)  # the add has found the existing artist and paused
    assert repo.delete(existing.id)  # last track of Solo / Only: prunes both unless the add is in
    delete_done.set()
    adder.join(10)

    assert added and added[0] is not None, "the add failed against the pruned artist"
    with factory() as session:
        assert session.execute(select(Artist.name)).scalars().all() == ["Solo"]
        assert session.execute(select(Album.title)).scalars().all() == ["Only"]
