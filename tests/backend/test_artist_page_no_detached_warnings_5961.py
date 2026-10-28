"""The artist page reads load what they serialise (#5961).

``get_by_id`` hydrated every Track of the artist and every album's tracks, yet not
``Album.artist``, so serialising each album logged a DetachedInstanceError warning.
The artist endpoints now read through ``get_page`` / ``get_track_rows`` (#5872);
this pins both halves: no Track rows are hydrated, and nothing warns.
"""

import logging
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Album, Artist, Track
from auralis.library.repositories.artist_repository import ArtistRepository
from routers.serializers_library import serialize_album


@pytest.fixture
def repo():
    db_path = Path(tempfile.mkdtemp()) / "library.db"
    assert MigrationManager(str(db_path)).migrate_to_latest()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        artist = Artist(name="Queen", normalized_name="queen")
        session.add(artist)
        session.flush()
        for a in range(3):
            album = Album(title=f"Album {a}", artist_id=artist.id, year=1970 + a)
            session.add(album)
            session.flush()
            for t in range(4):
                track = Track(
                    filepath=f"/tmp/{a}_{t}.flac", title=f"T{a}{t}", duration=100.0,
                    sample_rate=44100, channels=2, format="FLAC", album_id=album.id,
                )
                track.artists.append(artist)
                session.add(track)
        session.commit()
    statements: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda c, cur, stmt, *a: statements.append(stmt))
    repository = ArtistRepository(session_factory)
    repository.statements = statements  # type: ignore[attr-defined]
    return repository


def test_artist_page_serialises_albums_without_detached_warnings(repo, caplog):
    with caplog.at_level(logging.WARNING):
        artist = repo.get_page(1)
        serialized = [serialize_album(album) for album in artist.albums]

    assert len(serialized) == 3
    assert [r for r in caplog.records if "could not be loaded" in r.getMessage()] == []


def test_artist_page_does_not_hydrate_track_rows(repo):
    repo.statements.clear()

    repo.get_page(1)

    selected_from_tracks = [
        s for s in repo.statements
        if "FROM tracks" in s and "lyrics" in s  # a full Track hydration selects every column
    ]
    assert selected_from_tracks == []
