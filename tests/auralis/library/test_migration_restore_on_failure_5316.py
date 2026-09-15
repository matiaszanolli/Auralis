"""
A migration that fails partway is rolled back to its backup (#5316)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

check_and_migrate_database() backed the library up and then applied schema
steps one at a time. When a later step failed it only logged and returned
False, and restore_database() had no production caller. The library was left
at an intermediate version no released app targets, and every later start
failed against it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine

from auralis.__version__ import __db_schema_version__
from auralis.library import migration_manager
from auralis.library.migration_manager import (
    MigrationManager,
    check_and_migrate_database,
)
from auralis.library.models import SchemaVersion

START = __db_schema_version__ - 2


@pytest.fixture
def old_db(tmp_path) -> str:
    """A library two schema steps behind the app."""
    path = tmp_path / "library.db"
    manager = MigrationManager(str(path))
    manager.initialize_fresh_database()
    manager.close()

    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.execute(SchemaVersion.__table__.delete())
        conn.execute(
            SchemaVersion.__table__.insert(),
            {"version": START, "description": "older", "migration_script": "test"},
        )
    engine.dispose()
    return str(path)


def _version(db_path: str) -> int:
    manager = MigrationManager(db_path)
    try:
        return manager.get_current_version()
    finally:
        manager.close()


def _first_step_lands_then(outcome):
    """apply_migration stand-in: the first step is recorded, the second fails."""

    def apply(self, from_version, to_version):
        if from_version == START:
            self._record_migration(to_version, "step that landed")
            return True
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return apply


def _loud_messages(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


def test_a_failed_step_restores_the_backup(old_db, tmp_path, caplog):
    caplog.set_level(logging.DEBUG, logger=migration_manager.logger.name)
    restore = patch.object(
        migration_manager, "restore_database", wraps=migration_manager.restore_database
    )
    with patch.object(MigrationManager, "apply_migration", _first_step_lands_then(False)), \
            restore as restore_spy:
        assert check_and_migrate_database(old_db, auto_backup=True) is False

    assert _version(old_db) == START, "left at the intermediate version instead of restored"

    backup_path, restored_path = restore_spy.call_args.args
    assert restored_path == old_db
    assert Path(backup_path).name.startswith("library.backup_")

    loud = _loud_messages(caplog)
    assert any("Restored the database from its pre-migration backup" in m for m in loud)
    assert not any(str(tmp_path) in m for m in loud), "absolute path above DEBUG (#4929)"


def test_a_step_that_raises_restores_the_backup(old_db):
    with patch.object(
        MigrationManager, "apply_migration", _first_step_lands_then(RuntimeError("disk full"))
    ):
        assert check_and_migrate_database(old_db, auto_backup=True) is False

    assert _version(old_db) == START


def test_a_failed_restore_is_reported_as_an_error(old_db, caplog):
    caplog.set_level(logging.WARNING, logger=migration_manager.logger.name)
    with patch.object(MigrationManager, "apply_migration", _first_step_lands_then(False)), \
            patch.object(migration_manager, "restore_database", return_value=False):
        assert check_and_migrate_database(old_db, auto_backup=True) is False

    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("Could not restore the pre-migration backup" in m for m in errors)
    assert not any("Restored the database" in m for m in _loud_messages(caplog))


def test_without_a_backup_nothing_is_restored(old_db, caplog):
    caplog.set_level(logging.ERROR, logger=migration_manager.logger.name)
    with patch.object(MigrationManager, "apply_migration", _first_step_lands_then(False)), \
            patch.object(migration_manager, "restore_database") as restore:
        assert check_and_migrate_database(old_db, auto_backup=False) is False

    restore.assert_not_called()
    assert any("No pre-migration backup" in r.getMessage() for r in caplog.records)
