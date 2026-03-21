# -*- coding: utf-8 -*-

"""
Regression test for MigrationManager DDL+version atomicity (issue #2905)

Verifies that DDL changes and the schema_version INSERT execute in the same
transaction, so a failure in the version write rolls back the DDL too.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, inspect, text

from auralis.library.migration_manager import MigrationManager


@pytest.fixture
def temp_db():
    """Create a temporary database seeded at schema v1."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_library.db"

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE schema_version ("
            "  id INTEGER PRIMARY KEY,"
            "  version INTEGER NOT NULL UNIQUE,"
            "  applied_at TEXT,"
            "  description TEXT,"
            "  migration_script TEXT"
            ")"
        ))
        conn.execute(text(
            "INSERT INTO schema_version (version, description, migration_script) "
            "VALUES (1, 'Initial schema', 'initial')"
        ))
        conn.execute(text(
            "CREATE TABLE tracks (id INTEGER PRIMARY KEY, title TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE albums (id INTEGER PRIMARY KEY, name TEXT)"
        ))
    engine.dispose()

    yield str(db_path)
    shutil.rmtree(temp_dir, ignore_errors=True)


def _get_columns(db_path: str, table: str) -> set[str]:
    engine = create_engine(f"sqlite:///{db_path}")
    cols = {c["name"] for c in inspect(engine).get_columns(table)}
    engine.dispose()
    return cols


def _get_version(db_path: str) -> int:
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        ).fetchone()
    engine.dispose()
    return int(row[0]) if row else 0


def test_crash_during_version_write_rolls_back_ddl(temp_db):
    """If the version INSERT fails, DDL must also be rolled back.

    We patch datetime.now() — called inside apply_migration right before
    the version INSERT — to simulate a crash after DDL but before the
    version is recorded.
    """
    manager = MigrationManager(temp_db)

    # datetime.now() is called to produce `applied_at` just before the INSERT.
    # Making it raise simulates a crash between DDL and version write.
    with patch("auralis.library.migration_manager.datetime") as mock_dt:
        mock_dt.now.side_effect = RuntimeError("Simulated crash during version write")

        with pytest.raises(RuntimeError, match="Simulated crash"):
            manager.apply_migration(1, 2)

    manager.close()

    # DDL should have been rolled back — columns must NOT exist
    assert "lyrics" not in _get_columns(temp_db, "tracks"), (
        "DDL was committed despite version INSERT failure — not atomic"
    )
    assert _get_version(temp_db) == 1, (
        "Version should still be 1 after failed migration"
    )


def test_successful_migration_records_version_atomically(temp_db):
    """A successful migration records both DDL and version in one shot."""
    manager = MigrationManager(temp_db)

    success = manager.apply_migration(1, 2)
    assert success is True
    manager.close()

    # DDL applied
    assert "lyrics" in _get_columns(temp_db, "tracks")
    assert "artwork_path" in _get_columns(temp_db, "albums")

    # Version recorded
    assert _get_version(temp_db) == 2
