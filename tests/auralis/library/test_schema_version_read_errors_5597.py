"""
Regression: a failed schema-version read must not stamp an old database as current (#5597)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``get_current_version()`` mapped every exception to 0, and ``migrate_to_latest()``
reads 0 as "fresh database": it ran ``create_all`` (a no-op over existing tables)
and recorded the latest version, so one failed read skipped every migration and
the pre-migration backup. Only a missing ``schema_version`` table means "fresh".
"""

import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from auralis.__version__ import __db_schema_version__
from auralis.library.migration_manager import MigrationManager, check_and_migrate_database

OLD_VERSION = 10


def _stored_versions(db_path: Path) -> list[int]:
    with closing(sqlite3.connect(db_path)) as connection:
        return [v for (v,) in connection.execute("SELECT version FROM schema_version ORDER BY version")]


@pytest.fixture
def old_db(tmp_path: Path) -> Path:
    """A library whose schema_version says v10."""
    path = tmp_path / "old.db"
    with MigrationManager(str(path)) as manager:
        assert manager.initialize_fresh_database()
        with manager.engine.begin() as connection:
            connection.execute(text("DELETE FROM schema_version"))
            connection.execute(text(
                "INSERT INTO schema_version (version, description, migration_script) "
                f"VALUES ({OLD_VERSION}, 'old', 'old')"
            ))
    return path


def _locked() -> OperationalError:
    return OperationalError("SELECT ...", {}, sqlite3.OperationalError("database is locked"))


def test_a_failed_read_propagates_instead_of_reporting_a_fresh_database(old_db: Path) -> None:
    with MigrationManager(str(old_db)) as manager:
        with patch.object(manager, "_get_session", side_effect=_locked()):
            with pytest.raises(OperationalError, match="database is locked"):
                manager.get_current_version()


def test_migrate_to_latest_does_not_stamp_an_old_database_on_a_failed_read(old_db: Path) -> None:
    with MigrationManager(str(old_db)) as manager:
        with patch.object(manager, "_get_session", side_effect=_locked()):
            with pytest.raises(OperationalError):
                manager.migrate_to_latest()

    assert _stored_versions(old_db) == [OLD_VERSION]


def test_startup_check_reports_failure_and_leaves_the_version_alone(old_db: Path) -> None:
    with patch.object(MigrationManager, "get_current_version", side_effect=_locked()):
        assert check_and_migrate_database(str(old_db)) is False

    assert _stored_versions(old_db) == [OLD_VERSION]


def test_a_missing_version_table_still_means_a_fresh_database(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    with MigrationManager(str(path)) as manager:
        assert manager.get_current_version() == 0
        assert manager.migrate_to_latest()

    assert _stored_versions(path) == [__db_schema_version__]


def test_an_empty_version_table_still_means_a_fresh_database(old_db: Path) -> None:
    with MigrationManager(str(old_db)) as manager:
        with manager.engine.begin() as connection:
            connection.execute(text("DELETE FROM schema_version"))
        assert manager.get_current_version() == 0
