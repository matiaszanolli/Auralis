"""Pre-migration backups are pruned to the newest few (#5750).

Every migration wrote a full copy of the library beside it and nothing removed
one (465 files / 9.2 GB on a dev machine), until a full disk made the next
upgrade abort at startup because the backup step must succeed.
"""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine

from auralis.__version__ import __db_schema_version__
from auralis.library.migration_backup import backup_database
from auralis.library.migration_backup_retention import (
    KEEP_PRE_MIGRATION_BACKUPS,
    prune_old_backups,
)
from auralis.library.migration_manager import MigrationManager, check_and_migrate_database
from auralis.library.models import SchemaVersion


def _fake_backups(directory: Path, count: int, stem: str = "library", suffix: str = ".db") -> list[Path]:
    paths = []
    for i in range(count):
        path = directory / f"{stem}.backup_20260101_{i:06d}{suffix}"
        path.write_bytes(b"x")
        paths.append(path)
    return paths


def test_only_the_newest_backups_remain(tmp_path):
    (tmp_path / "library.db").write_bytes(b"db")
    backups = _fake_backups(tmp_path, KEEP_PRE_MIGRATION_BACKUPS + 3)

    removed = prune_old_backups(str(tmp_path / "library.db"))

    assert removed == 3
    assert sorted(p.name for p in tmp_path.glob("library.backup_*")) == sorted(
        p.name for p in backups[-KEEP_PRE_MIGRATION_BACKUPS:]
    )


def test_the_protected_backup_is_never_removed(tmp_path):
    (tmp_path / "library.db").write_bytes(b"db")
    backups = _fake_backups(tmp_path, 6)
    oldest = backups[0]

    prune_old_backups(str(tmp_path / "library.db"), keep=2, protect=str(oldest))

    assert oldest.exists()
    assert {p.name for p in tmp_path.glob("library.backup_*")} == {
        oldest.name, backups[-1].name, backups[-2].name,
    }


def test_files_that_only_resemble_the_pattern_are_left_alone(tmp_path):
    (tmp_path / "library.db").write_bytes(b"db")
    _fake_backups(tmp_path, 5)
    bystanders = [
        tmp_path / "library.backup_notes.db",
        tmp_path / "library.backup_20260101_123456.db.bak",
        tmp_path / "other.backup_20250101_000000.db",
        tmp_path / "library.backup_2026_01.db",
    ]
    for path in bystanders:
        path.write_bytes(b"keep")

    prune_old_backups(str(tmp_path / "library.db"), keep=1)

    assert all(p.exists() for p in bystanders)
    assert len(list(tmp_path.glob("library.backup_20260101_??????.db"))) == 1


def test_pruning_never_raises(tmp_path):
    assert prune_old_backups(str(tmp_path / "missing" / "library.db")) == 0


def test_the_writer_and_the_pruner_agree_on_the_name(tmp_path):
    db = tmp_path / "library.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE t (x)")
    written = Path(backup_database(str(db)))
    _fake_backups(tmp_path, 5)  # stamped 2026-01-01: all older than the one just written

    prune_old_backups(str(db), keep=1)

    assert written.exists(), "the pruner did not recognise the name backup_database writes"
    assert len(list(tmp_path.glob("library.backup_*"))) == 1


@pytest.fixture
def old_db(tmp_path) -> str:
    path = tmp_path / "library.db"
    manager = MigrationManager(str(path))
    manager.initialize_fresh_database()
    manager.close()
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.execute(SchemaVersion.__table__.delete())
        conn.execute(
            SchemaVersion.__table__.insert(),
            {"version": __db_schema_version__ - 1, "description": "older", "migration_script": "test"},
        )
    engine.dispose()
    return str(path)


def test_a_successful_migration_prunes_old_backups_and_keeps_its_own(old_db, tmp_path):
    stale = _fake_backups(tmp_path, KEEP_PRE_MIGRATION_BACKUPS + 4)
    # Pretend those are from 2026-01-01; this run's backup is stamped now (newer).

    assert check_and_migrate_database(old_db, auto_backup=True) is True

    remaining = sorted(tmp_path.glob("library.backup_*"))
    assert len(remaining) == KEEP_PRE_MIGRATION_BACKUPS
    assert remaining[-1].name > stale[-1].name, "this run's backup is the newest and survives"


def test_a_failed_migration_does_not_prune(old_db, tmp_path):
    stale = _fake_backups(tmp_path, KEEP_PRE_MIGRATION_BACKUPS + 4)

    with patch.object(MigrationManager, "migrate_to_latest", return_value=False):
        assert check_and_migrate_database(old_db, auto_backup=True) is False

    assert len(list(tmp_path.glob("library.backup_*"))) == len(stale) + 1
