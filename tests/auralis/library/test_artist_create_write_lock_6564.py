"""Concurrent first inserts of an artist's spelling variants make one row (#6564).

_get_or_create_artists looks an artist up by normalized_name and inserts with
ON CONFLICT DO NOTHING, but only artists.name is UNIQUE. When two adds of
"AC/DC" and "ACDC" both missed the lookup, the second insert succeeded (the
names differ), so the first add's `.one()` re-select found two rows, raised,
and that track was silently not added (add() returned None). add() and update()
now take the write lock before the lookup, so the second waits for the first
and finds its row. The test forces that interleaving: the first add pauses
right after its artist lookup until the second add finishes (or 0.5 s pass).
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest
from sqlalchemy import Select, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Artist
from auralis.library.repositories.track_repository import TrackRepository


@pytest.fixture
def tracks():
    db_path = Path(tempfile.mkdtemp()) / "library.db"
    manager = MigrationManager(str(db_path))
    assert manager.migrate_to_latest()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 10})
    factory = sessionmaker(bind=engine)
    yield TrackRepository(factory), factory
    engine.dispose()
    manager.close()


def _info(path, artist):
    return {"filepath": path, "title": f"Song by {artist}", "artists": [artist], "duration": 60.0,
            "sample_rate": 44100, "channels": 2, "format": "FLAC"}


def _selects_artists(statement):
    return isinstance(statement, Select) and any(
        desc.get("entity") is Artist for desc in statement.column_descriptions
    )


def test_spelling_variants_added_concurrently_share_one_artist(tracks, monkeypatch):
    repo, factory = tracks
    second_done = threading.Event()
    paused = []
    real_execute = Session.execute

    def execute(self, statement, *args, **kwargs):
        result = real_execute(self, statement, *args, **kwargs)
        if not paused and _selects_artists(statement):
            paused.append(threading.current_thread().name)
            second_done.wait(0.5)
        return result

    monkeypatch.setattr(Session, "execute", execute)

    first_result = []
    first = threading.Thread(target=lambda: first_result.append(repo.add(_info("/music/a.flac", "AC/DC"))))
    first.start()
    threading.Event().wait(0.1)  # let the first add reach its paused artist lookup
    assert repo.add(_info("/music/b.flac", "ACDC")) is not None
    second_done.set()
    first.join(10)

    assert first_result and first_result[0] is not None, "the first add was lost to the race"
    with factory() as session:
        rows = session.execute(select(Artist.name).where(Artist.normalized_name == "acdc")).all()
    assert len(rows) == 1, f"duplicate artists for one normalized name: {rows}"
