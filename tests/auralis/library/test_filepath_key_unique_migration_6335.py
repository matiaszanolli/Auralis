"""v31 -> v32 makes tracks.filepath_key unique on upgraded databases (#6335).

v017->v018 created ix_tracks_filepath_key non-unique, so an upgraded library could hold two rows for
one file (case-variant spellings added concurrently, or a relocation onto an existing key), unlike a
fresh create_all database. The migration merges such rows onto the lowest id, then builds the index.
"""

import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import Float, Integer, LargeBinary, String, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import auralis.library.migrations as migrations_pkg
from auralis.__version__ import __db_schema_version__
from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Artist, Playlist, Track, TrackFingerprint
from auralis.library.models.base import track_playlist

MIGRATIONS = Path(migrations_pkg.__file__).parent


def _track(track_id: int, key: str | None, **extra) -> Track:
    return Track(
        id=track_id, title=f"T{track_id}", filepath=f"/music/{track_id}.flac", filepath_key=key,
        duration=10.0, sample_rate=44100, channels=2, format="FLAC", filesize=64, **extra,
    )


def _fingerprint(track_id: int) -> TrackFingerprint:
    values: dict[str, object] = {}
    for column in TrackFingerprint.__table__.columns:
        if column.primary_key or column.nullable or column.server_default is not None or column.name == "track_id":
            continue
        kind = column.type
        values[column.name] = (
            0.0 if isinstance(kind, Float) else 0 if isinstance(kind, Integer)
            else b"" if isinstance(kind, LargeBinary) else "x" if isinstance(kind, String) else None
        )
    return TrackFingerprint(track_id=track_id, **values)


def _v31_library(db_path: Path) -> None:
    """A v31 library whose key index is non-unique and which holds three rows for one file."""
    with MigrationManager(str(db_path)) as manager:
        assert manager.initialize_fresh_database()
        with manager.engine.begin() as conn:
            conn.execute(text("UPDATE schema_version SET version = 31"))
            conn.execute(text("DROP INDEX ix_tracks_filepath_key"))
            conn.execute(text("CREATE INDEX ix_tracks_filepath_key ON tracks(filepath_key)"))
        with sessionmaker(bind=manager.engine)() as session:
            session.add_all([
                _track(1, "song", play_count=2, favorite=False, last_played=datetime(2026, 1, 1)),
                _track(2, "song", play_count=3, favorite=True, last_played=datetime(2026, 3, 1)),
                _track(3, "song", play_count=5, favorite=False, last_played=None),
                _track(4, "other", play_count=7),
                _track(5, None), _track(6, None),  # NULL keys are distinct in a unique index
            ])
            session.add(Artist(id=1, name="Dup Artist", normalized_name="dup artist"))
            session.flush()
            for number in (1, 2, 3):
                session.add(Playlist(id=number, name=f"P{number}"))
            session.flush()
            session.execute(track_playlist.insert(), [
                {"track_id": 1, "playlist_id": 1, "position": 0},
                {"track_id": 2, "playlist_id": 1, "position": 1},  # P1 holds both duplicates
                {"track_id": 3, "playlist_id": 2, "position": 0},
                {"track_id": 2, "playlist_id": 3, "position": 0},
                {"track_id": 4, "playlist_id": 3, "position": 1},
            ])
            session.execute(text("INSERT INTO track_artist (track_id, artist_id) VALUES (1, 1), (2, 1)"))
            session.add(_fingerprint(3))  # only a duplicate was ever fingerprinted
            session.execute(text(
                "INSERT INTO similarity_graph (track_id, similar_track_id, distance, similarity_score, rank) "
                "VALUES (3, 4, 0.1, 0.9, 1), (4, 2, 0.1, 0.9, 1), (4, 1, 0.2, 0.8, 2)"
            ))
            session.commit()


def _rows(db_path: Path, sql: str) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


@pytest.fixture
def migrated(tmp_path):
    db_path = tmp_path / "library.db"
    _v31_library(db_path)
    with MigrationManager(str(db_path)) as manager:
        assert manager.migrate_to_latest()
        assert manager.get_current_version() == __db_schema_version__
    return db_path


def test_rows_sharing_a_key_are_merged_onto_the_lowest_id(migrated):
    assert _rows(migrated, "SELECT id FROM tracks ORDER BY id") == [(1,), (4,), (5,), (6,)]


def test_play_count_is_summed_and_favorite_and_last_played_are_kept(migrated):
    assert _rows(migrated, "SELECT play_count, favorite, last_played FROM tracks WHERE id = 1") == [
        (10, 1, "2026-03-01 00:00:00.000000"),
    ]
    assert _rows(migrated, "SELECT play_count FROM tracks WHERE id = 4") == [(7,)]


def test_playlist_membership_moves_to_the_survivor_without_doubling(migrated):
    assert _rows(migrated, "SELECT playlist_id, track_id FROM track_playlist ORDER BY playlist_id, track_id") == [
        (1, 1), (2, 1), (3, 1), (3, 4),
    ]


def test_a_missing_fingerprint_moves_to_the_survivor_and_stale_edges_go(migrated):
    assert _rows(migrated, "SELECT track_id FROM track_fingerprints") == [(1,)]
    assert _rows(migrated, "SELECT track_id, similar_track_id FROM similarity_graph") == [(4, 1)]
    assert _rows(migrated, "SELECT track_id FROM track_artist") == [(1,)]


def test_the_index_is_unique_like_a_fresh_database(migrated):
    sql = _rows(migrated, "SELECT sql FROM sqlite_master WHERE name = 'ix_tracks_filepath_key'")[0][0]
    assert "UNIQUE" in sql.upper()

    with MigrationManager(str(migrated)) as manager:
        with sessionmaker(bind=manager.engine)() as session:
            session.add(_track(9, "song"))
            with pytest.raises(IntegrityError):
                session.commit()


def test_a_library_without_duplicates_is_unchanged_and_nulls_stay_distinct(tmp_path):
    db_path = tmp_path / "library.db"
    _v31_library(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM tracks WHERE id IN (2, 3)")
    conn.execute("DELETE FROM track_playlist WHERE track_id IN (2, 3)")
    conn.execute("DELETE FROM track_artist WHERE track_id = 2")
    conn.execute("DELETE FROM track_fingerprints WHERE track_id = 3")
    conn.execute("DELETE FROM similarity_graph WHERE track_id = 3 OR similar_track_id = 2")
    conn.commit()
    conn.close()

    with MigrationManager(str(db_path)) as manager:
        assert manager.migrate_to_latest()

    assert _rows(db_path, "SELECT id, play_count FROM tracks ORDER BY id") == [(1, 2), (4, 7), (5, 0), (6, 0)]


def test_the_migration_is_a_forward_step_at_the_head_of_the_chain():
    files = sorted(p.name for p in MIGRATIONS.glob("migration_v*_to_v*.sql"))
    edges = [tuple(int(n) for n in re.findall(r"v(\d+)_to_v(\d+)", f)[0]) for f in files]

    assert (31, 32) in edges
    assert max(to for _, to in edges) == __db_schema_version__
