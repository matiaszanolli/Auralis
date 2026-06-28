"""
MigrationManager SQL-validation regressions (discovered fixing #4139).

Two bugs blocked migration_v015_to_v016 (and any recreate-and-copy migration),
so the DB could not reach v16 and the app failed to start on a v15 database:

1. DROP TABLE was rejected unless the migration declared `-- @ALLOW_DROP_TABLE`;
   v016 needs the SQLite recreate-and-copy idiom but lacked the marker.
2. The unqualified-DELETE guard used re.MULTILINE, so `$` matched end-of-line and
   a valid multi-line `DELETE FROM t\nWHERE ...` was wrongly flagged.
"""

from sqlalchemy import text

from auralis.library.migration_manager import MigrationManager
from auralis.library.models import SchemaVersion


def _manager(tmp_path):
    db = tmp_path / "mig.db"
    m = MigrationManager(str(db))
    # apply_migration records into schema_version; create it for the test DB.
    SchemaVersion.__table__.create(m.engine, checkfirst=True)
    m.migrations_dir = tmp_path / "migs"
    m.migrations_dir.mkdir()
    return m


def _write_migration(m, sql):
    (m.migrations_dir / "migration_v100_to_v101.sql").write_text(sql)


def _create_table(m, ddl):
    with m.engine.begin() as conn:
        conn.execute(text(ddl))


def test_multiline_delete_where_is_not_flagged_unqualified(tmp_path):
    m = _manager(tmp_path)
    _create_table(m, "CREATE TABLE t (id INTEGER, k INTEGER)")
    _write_migration(
        m,
        "DELETE FROM t\n"
        "WHERE id NOT IN (SELECT MIN(id) FROM t GROUP BY k);\n",
    )
    assert m.apply_migration(100, 101) is True


def test_unqualified_delete_is_rejected(tmp_path):
    m = _manager(tmp_path)
    _create_table(m, "CREATE TABLE t (id INTEGER)")
    _write_migration(m, "DELETE FROM t;\n")
    assert m.apply_migration(100, 101) is False


def test_drop_table_without_marker_is_rejected(tmp_path):
    m = _manager(tmp_path)
    _create_table(m, "CREATE TABLE t (id INTEGER)")
    _write_migration(m, "DROP TABLE t;\n")
    assert m.apply_migration(100, 101) is False


def test_drop_table_with_allow_marker_is_permitted(tmp_path):
    m = _manager(tmp_path)
    _create_table(m, "CREATE TABLE t (id INTEGER)")
    _write_migration(m, "-- @ALLOW_DROP_TABLE\nDROP TABLE t;\n")
    assert m.apply_migration(100, 101) is True
