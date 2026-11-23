"""A refused owner-only chmod is reported, not swallowed (#6543).

The library directory, the database, its WAL sidecars and the migration backup
are restricted to owner-only access (#2577, #4347, #4824, #5333), but every
failure was ``except OSError: pass``: on exFAT, some network mounts or a file
owned by someone else the library stayed readable with no signal. All four
sites now go through ``restrict_to_owner``, which logs one WARNING naming the
file (never the full path), and startup carries on.
"""

import logging
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from auralis.library import database_engine
from auralis.library.database_engine import create_library_engine, restrict_wal_sidecars
from auralis.library.migration_backup import backup_database


@pytest.fixture
def refused_chmod(monkeypatch, caplog):
    def chmod(path, mode):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(os, "chmod", chmod)
    caplog.set_level(logging.WARNING, logger="auralis")
    return caplog


def _warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING and "owner-only" in r.getMessage()]


def _db(tmp: Path) -> Path:
    db = tmp / "library.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE t (x)")
    return db


def test_database_chmod_refusal_warns_once_by_name_and_continues(refused_chmod):
    tmp = Path(tempfile.mkdtemp())
    engine = create_library_engine(str(_db(tmp)))
    engine.dispose()

    messages = _warnings(refused_chmod)
    assert len(messages) == 1
    assert "library.db" in messages[0] and "Operation not permitted" in messages[0]
    assert str(tmp) not in messages[0]


def test_sidecar_and_backup_chmod_refusals_warn(refused_chmod):
    tmp = Path(tempfile.mkdtemp())
    db = _db(tmp)
    for suffix in ("-wal", "-shm"):
        Path(str(db) + suffix).write_bytes(b"")

    restrict_wal_sidecars(str(db))
    backup = backup_database(str(db), str(tmp / "backups"))

    messages = _warnings(refused_chmod)
    assert any("library.db-wal" in m for m in messages)
    assert any("library.db-shm" in m for m in messages)
    assert any(Path(backup).name in m for m in messages)
    assert not any(str(tmp) in m for m in messages)


def test_all_hardening_sites_share_the_helper():
    """CONSISTENCY: no chmod-and-pass copy is left in either module."""
    import inspect

    from auralis.library import migration_backup

    for module in (database_engine, migration_backup):
        source = inspect.getsource(module)
        assert source.count("os.chmod(") == (1 if module is database_engine else 0), module.__name__
