"""#5557 — bulk track deletes must clear the association tables.

``track_artist`` / ``track_genre`` / ``track_playlist`` reference ``tracks.id``
without ``ON DELETE CASCADE`` and SQLite runs with foreign_keys=ON, so
``cleanup_missing_files()`` and ``remove_tracks_under_folder()`` (a Core
``DELETE FROM tracks``) raised a FOREIGN KEY error for any track that had an
artist, genre or playlist row. Their callers swallow the exception, so the
#5458 / #5467 prunes silently did nothing for nearly every real track.
"""

from pathlib import Path

import pytest
from sqlalchemy import func, select

from auralis.library.models import Track, track_artist, track_genre, track_playlist


def _info(path: Path, name: str, artist: str, genre: str) -> dict:
    return {
        'title': name, 'filepath': str(path), 'sample_rate': 44100, 'channels': 2,
        'format': 'MP3', 'artists': [artist], 'genres': [genre], 'album': f'{name} album',
    }


def _count(session_factory, table) -> int:
    with session_factory() as session:
        return int(session.execute(select(func.count()).select_from(table)).scalar_one())


def _track_count(session_factory) -> int:
    with session_factory() as session:
        return int(session.execute(select(func.count()).select_from(Track)).scalar_one())


def _associations(session_factory) -> dict[str, int]:
    return {t.name: _count(session_factory, t) for t in (track_artist, track_genre, track_playlist)}


@pytest.fixture
def track_repository(library_database):
    # The production LibraryDatabase, which runs with PRAGMA foreign_keys=ON.
    # The plain session_factory fixture does not enforce foreign keys, so it
    # would only expose the orphaned association rows, not the FOREIGN KEY
    # error the bug raised in the app.
    return library_database.tracks


@pytest.fixture
def playlist_repository(library_database):
    return library_database.playlists


@pytest.fixture
def session_factory(library_database):
    return library_database.SessionLocal


@pytest.fixture
def library(track_repository, playlist_repository, tmp_path):
    """Three tracks (two under ``gone/``, one under ``kept/``), all in a playlist."""
    gone, kept = tmp_path / 'gone', tmp_path / 'kept'
    gone.mkdir()
    kept.mkdir()
    # None of the files exist on disk; the parent directories do, so
    # cleanup_missing_files treats them as genuinely missing, not unmounted.
    ids = [
        int(track_repository.add(_info(gone / 'a.mp3', 'a', 'Band A', 'Rock')).id),
        int(track_repository.add(_info(gone / 'b.mp3', 'b', 'Band B', 'Jazz')).id),
        int(track_repository.add(_info(kept / 'c.mp3', 'c', 'Band C', 'Rock')).id),
    ]
    playlist = playlist_repository.create('mix')
    for track_id in ids:
        assert playlist_repository.add_track(playlist.id, track_id)
    return {'ids': ids, 'gone': gone, 'kept': kept}


def test_database_enforces_foreign_keys(session_factory):
    with session_factory() as session:
        assert session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_fixture_really_has_association_rows(library, session_factory):
    assert _associations(session_factory) == {'track_artist': 3, 'track_genre': 3, 'track_playlist': 3}


def test_cleanup_missing_files_removes_tracks_with_relationships(library, track_repository, session_factory):
    removed = track_repository.cleanup_missing_files()
    assert removed == 3
    assert _track_count(session_factory) == 0
    assert _associations(session_factory) == {'track_artist': 0, 'track_genre': 0, 'track_playlist': 0}


def test_remove_tracks_under_folder_removes_only_that_folder(library, track_repository, session_factory):
    removed = track_repository.remove_tracks_under_folder(str(library['gone']))
    assert removed == 2
    assert _track_count(session_factory) == 1
    # The surviving track keeps all of its relationships.
    assert _associations(session_factory) == {'track_artist': 1, 'track_genre': 1, 'track_playlist': 1}


def test_single_delete_still_clears_associations(library, track_repository, session_factory):
    assert track_repository.delete(library['ids'][0]) is True
    assert _track_count(session_factory) == 2
    assert _associations(session_factory) == {'track_artist': 2, 'track_genre': 2, 'track_playlist': 2}
    assert track_repository.delete(library['ids'][0]) is False  # already gone


def test_delete_tracks_by_ids_edge_cases(library, track_repository, session_factory):
    from auralis.library.repositories.track_deletion import delete_tracks_by_ids

    with session_factory() as session:
        assert delete_tracks_by_ids(session, []) == 0
        assert delete_tracks_by_ids(session, [10**9]) == 0  # unknown ids are not an error
        session.commit()
    assert _track_count(session_factory) == 3


def test_all_bulk_track_deletes_go_through_the_helper():
    """No other repository module may issue its own ``delete(Track)``."""
    root = Path(__file__).resolve().parents[3] / 'auralis' / 'library' / 'repositories'
    offenders = [
        p.name for p in root.glob('*.py')
        if 'delete(Track)' in p.read_text() and p.name not in ('track_deletion.py', 'factory.py')
    ]
    assert offenders == []
