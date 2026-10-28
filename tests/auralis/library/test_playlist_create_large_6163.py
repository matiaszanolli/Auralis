"""Regression test: creating a playlist from more ids than SQLite can bind (#6163).

MAX_TRACK_ID_LIST (50,000) is above SQLite's bound-variable limit (32,766), and
create() resolved the ids with one ``IN (...)``, so a documented-valid request
failed with "too many SQL variables" and the route answered 400.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import create_engine, insert
from sqlalchemy.orm import sessionmaker

from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Track
from auralis.library.repositories.playlist_repository import PlaylistRepository

TRACK_COUNT = 40_000  # past 32,766


def test_create_with_more_ids_than_sqlite_variables_keeps_order_and_skips_unknown():
    db_path = Path(tempfile.mkdtemp()) / "library.db"
    assert MigrationManager(str(db_path)).migrate_to_latest()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        session.execute(insert(Track), [
            {"id": i, "filepath": f"/tmp/t{i}.flac", "title": f"T{i}",
             "duration": 1.0, "sample_rate": 44100, "channels": 2, "format": "FLAC"}
            for i in range(1, TRACK_COUNT + 1)
        ])
        session.commit()

    wanted = list(range(TRACK_COUNT, 0, -1)) + [TRACK_COUNT + 5]  # reversed + one unknown id
    playlist = PlaylistRepository(session_factory).create("Big", track_ids=wanted)

    assert playlist is not None
    assert [t.id for t in playlist.tracks][:3] == [TRACK_COUNT, TRACK_COUNT - 1, TRACK_COUNT - 2]
    assert len(playlist.tracks) == TRACK_COUNT
