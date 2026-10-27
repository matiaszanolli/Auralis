"""
Regression: track_fingerprints.fingerprint_blob reaches databases that predate it (#5718)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ORM column was added with no migration, and create_all() never alters an
existing table, so a library whose table came from the v003->v004 SQL migration
failed every fingerprint read with "no such column" and recomputed forever.
"""

import re
import sqlite3
from pathlib import Path

from sqlalchemy import text

import auralis.library.migrations as migrations_pkg
from auralis.__version__ import __db_schema_version__
from auralis.library.database import LibraryDatabase
from auralis.library.migration_manager import MigrationManager
from auralis.library.models import TrackFingerprint

MIGRATIONS = Path(migrations_pkg.__file__).parent


def _columns(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(track_fingerprints)")}
    finally:
        conn.close()


def _database_at_v28_without_the_column(db_path: Path) -> None:
    """A library as an old release left it: a v28 schema whose fingerprint
    table has no fingerprint_blob."""
    with MigrationManager(str(db_path)) as manager:
        assert manager.initialize_fresh_database()
        with manager.engine.begin() as conn:
            conn.execute(text("ALTER TABLE track_fingerprints DROP COLUMN fingerprint_blob"))
            conn.execute(text("UPDATE schema_version SET version = 28"))
    assert "fingerprint_blob" not in _columns(db_path)


def test_migration_adds_the_column_and_fingerprint_reads_work(tmp_path):
    db_path = tmp_path / "old.db"
    _database_at_v28_without_the_column(db_path)

    with MigrationManager(str(db_path)) as manager:
        assert manager.get_current_version() == 28
        assert manager.migrate_to_latest()
        assert manager.get_current_version() == __db_schema_version__

    assert "fingerprint_blob" in _columns(db_path)

    db = LibraryDatabase(str(db_path))
    try:
        assert db.fingerprints.get_by_track_id(1) is None  # was OperationalError: no such column
    finally:
        db.shutdown()


def test_library_database_open_upgrades_an_old_database(tmp_path):
    db_path = tmp_path / "old.db"
    _database_at_v28_without_the_column(db_path)

    db = LibraryDatabase(str(db_path))  # check_and_migrate_database runs in __init__
    try:
        assert db.fingerprints.get_count() == 0
    finally:
        db.shutdown()
    assert "fingerprint_blob" in _columns(db_path)


def test_database_that_already_has_the_column_still_migrates(tmp_path):
    """Duplicate-column tolerance: fresh installs and hand-patched DBs."""
    db_path = tmp_path / "patched.db"
    with MigrationManager(str(db_path)) as manager:
        assert manager.initialize_fresh_database()
        with manager.engine.begin() as conn:
            conn.execute(text("UPDATE schema_version SET version = 28"))
    assert "fingerprint_blob" in _columns(db_path)

    with MigrationManager(str(db_path)) as manager:
        assert manager.migrate_to_latest()
        assert manager.get_current_version() == __db_schema_version__


def test_migration_chain_has_exactly_one_head_at_the_declared_version():
    files = sorted(p.name for p in MIGRATIONS.glob("migration_v*_to_v*.sql"))
    edges = [tuple(int(n) for n in re.findall(r"v(\d+)_to_v(\d+)", f)[0]) for f in files]

    assert len({src for src, _ in edges}) == len(edges), "two migrations share a source version"
    assert max(dst for _, dst in edges) == __db_schema_version__


def test_every_model_column_is_reachable_through_the_sql_migration_chain():
    """track_fingerprints is created by v003->v004 SQL; every column the model
    declares must be in that CREATE TABLE or added by a later ADD COLUMN, or an
    old database lacks it (this is how fingerprint_blob went missing)."""
    created = (MIGRATIONS / "migration_v003_to_v004.sql").read_text()
    body = re.search(
        r"CREATE TABLE(?: IF NOT EXISTS)? track_fingerprints\s*\((.*?)\n\);", created, re.S | re.I
    ).group(1)
    reachable = {
        m.group(1) for m in re.finditer(r"^\s*(\w+)\s+[A-Z]+", body, re.M)
    }
    for sql in sorted(MIGRATIONS.glob("migration_v*_to_v*.sql")):
        reachable |= set(re.findall(
            r"ALTER TABLE track_fingerprints ADD COLUMN (\w+)", sql.read_text(), re.I
        ))

    missing = {c.name for c in TrackFingerprint.__table__.columns} - reachable
    assert not missing, f"model columns no SQL migration provides: {sorted(missing)}"
