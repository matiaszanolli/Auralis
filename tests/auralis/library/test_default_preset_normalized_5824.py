"""Schema v23 normalizes user_settings.default_preset (#5824).

The 2026-09-13 preset narrowing shipped without a data migration, so rows
written before it could still hold a removed preset name (or NULL) and three
read sites degraded the value with a warning on every boot. v23 rewrites the
column once; the read-side tolerance is gone.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from auralis.__version__ import __db_schema_version__
from auralis.library.migration_manager import MigrationManager

PRE_NORMALIZATION_VERSION = 22


def _insert_settings_row(conn: sqlite3.Connection, stored_preset: str | None) -> None:
    """Insert one row, filling NOT NULL columns that only the ORM defaults."""
    values: dict[str, object] = {"id": 1, "default_preset": stored_preset}
    for _cid, name, col_type, notnull, default, _pk in conn.execute("PRAGMA table_info(user_settings)"):
        if name in values or not notnull or default is not None:
            continue
        values[name] = "" if "CHAR" in col_type.upper() or "TEXT" in col_type.upper() else 0
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    conn.execute(f"INSERT INTO user_settings ({columns}) VALUES ({marks})", tuple(values.values()))


def _db_at_v22(tmp_path: Path, stored_preset: str | None) -> Path:
    """A fresh latest-schema database rolled back to v22 with one legacy settings row."""
    db_path = tmp_path / "library.db"
    with MigrationManager(str(db_path)) as manager:
        assert manager.migrate_to_latest()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM user_settings")
        _insert_settings_row(conn, stored_preset)
        # A fresh database records a single row at the head version; rewind it.
        conn.execute("UPDATE schema_version SET version = ?", (PRE_NORMALIZATION_VERSION,))
        conn.commit()
    finally:
        conn.close()
    return db_path


def _stored_preset(db_path: Path) -> str | None:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT default_preset FROM user_settings WHERE id = 1").fetchone()[0]
    finally:
        conn.close()


def test_this_migration_is_the_current_head_or_earlier() -> None:
    assert __db_schema_version__ >= 23


@pytest.mark.parametrize("legacy", ["gentle", "warm", "bright", "punchy", "live", "vintage", "", None])
def test_every_legacy_value_is_rewritten_to_adaptive(tmp_path: Path, legacy: str | None) -> None:
    db_path = _db_at_v22(tmp_path, legacy)

    with MigrationManager(str(db_path)) as manager:
        assert manager.get_current_version() == PRE_NORMALIZATION_VERSION
        assert manager.migrate_to_latest()
        assert manager.get_current_version() == __db_schema_version__

    assert _stored_preset(db_path) == "adaptive"


def test_an_already_adaptive_row_is_untouched(tmp_path: Path) -> None:
    db_path = _db_at_v22(tmp_path, "adaptive")

    with MigrationManager(str(db_path)) as manager:
        assert manager.migrate_to_latest()

    assert _stored_preset(db_path) == "adaptive"
