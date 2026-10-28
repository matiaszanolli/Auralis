"""The artwork route reads one column, not the album's whole graph (#5896)."""

import tempfile
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Album, Artist, Track
from auralis.library.repositories.album_repository import AlbumRepository


def _repo():
    db_path = Path(tempfile.mkdtemp()) / "library.db"
    assert MigrationManager(str(db_path)).migrate_to_latest()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        artist = Artist(name="A", normalized_name="a")
        session.add(artist)
        session.flush()
        with_art = Album(id=1, title="Has art", artist_id=artist.id, artwork_path="/art/a.jpg")
        without = Album(id=2, title="No art", artist_id=artist.id)
        session.add_all([with_art, without])
        session.flush()
        for i in range(5):
            session.add(Track(
                filepath=f"/m/{i}.flac", title=f"T{i}", duration=1.0, sample_rate=44100,
                channels=2, format="FLAC", album_id=1,
            ))
        session.commit()
    statements: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda conn, cur, stmt, *args: statements.append(stmt))
    repo = AlbumRepository(session_factory)
    return repo, statements


def test_returns_existence_and_path():
    repo, _ = _repo()

    assert repo.get_artwork_path(1) == (True, "/art/a.jpg")
    assert repo.get_artwork_path(2) == (True, None)
    assert repo.get_artwork_path(99) == (False, None)


def test_runs_one_statement_that_touches_no_track_or_artist_table():
    repo, statements = _repo()
    statements.clear()

    repo.get_artwork_path(1)

    assert len(statements) == 1
    assert "tracks" not in statements[0] and "artists" not in statements[0]
