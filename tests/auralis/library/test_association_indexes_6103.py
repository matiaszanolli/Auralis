"""
Association-table indexes on fresh and migrated databases (#6103)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SQLite FOREIGN KEY constraints index only the parent key, never the child
column, so ``track_artist`` / ``track_genre`` (bare ``Table(...)`` with FK
columns only) and ``albums.artist_id`` had no index at all: every
``Track.artists``/``Track.genres`` join, selectinload and ``.any()`` EXISTS
was a full-table scan, and ``find_similar`` — run on every library track
load while ``auto_reference_selection`` is on — took 20-40 s at 50k tracks.

v024→v025 creates the indexes for upgraded databases; the model
declarations cover fresh ``create_all`` databases.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text

from auralis.library.migration_manager import MigrationManager
from auralis.library.schema_indexes import create_missing_declared_indexes

#: table -> {index name -> the column it must cover}
EXPECTED_INDEXES = {
    'track_artist': {
        'ix_track_artist_track_id': 'track_id',
        'ix_track_artist_artist_id': 'artist_id',
    },
    'track_genre': {
        'ix_track_genre_track_id': 'track_id',
        'ix_track_genre_genre_id': 'genre_id',
    },
    'albums': {
        'idx_albums_artist_id': 'artist_id',
    },
}


def _index_columns(engine, table: str) -> dict[str, list[str]]:
    """Map index name -> indexed columns for one table via PRAGMA."""
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA index_list({table})")).fetchall()
        result = {}
        for row in rows:
            name = row[1]
            cols = [
                r[2]
                for r in conn.execute(text(f"PRAGMA index_info({name})")).fetchall()
            ]
            result[name] = cols
        return result


def _assert_expected_indexes(engine) -> None:
    for table, expected in EXPECTED_INDEXES.items():
        indexes = _index_columns(engine, table)
        for name, column in expected.items():
            assert name in indexes, (
                f"{table} is missing index {name}; has {sorted(indexes)}"
            )
            assert column in indexes[name], (
                f"{table}.{name} must cover {column}, covers {indexes[name]}"
            )


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_library.db"
    yield str(db_path)
    shutil.rmtree(temp_dir, ignore_errors=True)


def _drop_expected_indexes(engine) -> None:
    with engine.begin() as conn:
        for table, names in EXPECTED_INDEXES.items():
            for name in names:
                conn.execute(text(f"DROP INDEX IF EXISTS {name}"))


def _set_schema_version(engine, version: int) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE schema_version SET version = {version}"))


def test_fresh_database_has_association_indexes(temp_db):
    """Fresh create_all databases get the indexes from the model
    declarations (schema_indexes repair covers any drift)."""
    with MigrationManager(temp_db) as manager:
        assert manager.initialize_fresh_database()
        create_missing_declared_indexes(manager.engine)
        # The repair must be a no-op on a fresh database
        _assert_expected_indexes(manager.engine)


def test_repair_creates_declared_indexes(temp_db):
    """create_missing_declared_indexes() recreates the indexes on a
    database that predates the declarations (#5321 mechanism)."""
    with MigrationManager(temp_db) as manager:
        assert manager.initialize_fresh_database()
        _drop_expected_indexes(manager.engine)
        created = create_missing_declared_indexes(manager.engine)
        assert set(created) >= {
            name for names in EXPECTED_INDEXES.values() for name in names
        }
        _assert_expected_indexes(manager.engine)


def test_v024_to_v025_migration_creates_indexes(temp_db):
    """A database at v24 (the version before the fix) migrates forward and
    ends up with the same indexes as a fresh database."""
    with MigrationManager(temp_db) as manager:
        assert manager.initialize_fresh_database()
        # Simulate a pre-v025 database: same tables, no new indexes, and the
        # recorded version rolled back to 24.
        _drop_expected_indexes(manager.engine)
        _set_schema_version(manager.engine, 24)

    with MigrationManager(temp_db) as manager:
        assert manager.get_current_version() == 24
        assert manager.migrate_to_latest()
        _assert_expected_indexes(manager.engine)


def test_artist_lookup_no_longer_full_scans(temp_db):
    """EXPLAIN QUERY PLAN for the artist_id lookup must use the index, not
    SCAN track_artist (the 20-40 s find_similar pattern)."""
    with MigrationManager(temp_db) as manager:
        assert manager.initialize_fresh_database()
        create_missing_declared_indexes(manager.engine)
        with manager.engine.connect() as conn:
            plan_rows = conn.execute(
                text("EXPLAIN QUERY PLAN SELECT track_id FROM track_artist "
                     "WHERE artist_id = 1")
            ).fetchall()
        plan = " ".join(str(row) for row in plan_rows)
        assert 'SCAN track_artist' not in plan, plan
        assert 'ix_track_artist_artist_id' in plan, plan


def test_migration_is_idempotent(temp_db):
    """Running the migration steps twice must not fail (CREATE INDEX IF NOT
    EXISTS) and the declared-index repair must stay a no-op afterwards."""
    with MigrationManager(temp_db) as manager:
        assert manager.initialize_fresh_database()
        _set_schema_version(manager.engine, 24)
        assert manager.migrate_to_latest()
        assert create_missing_declared_indexes(manager.engine) == []
