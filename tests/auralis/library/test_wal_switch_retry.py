"""
The WAL switch in every engine's connect hook survives lock contention
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ten threads opening a fresh library made ~3% of runs fail with MigrationError:
one connection's ``PRAGMA journal_mode=WAL`` got "database is locked" straight
away. SQLite skips the busy timeout when waiting could deadlock, so the hook
itself has to retry. A connection opened with ``timeout=0`` sees the same
immediate error from an ordinary lock, which makes the retry testable without
racing threads.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sqlite3
import threading
from pathlib import Path

import pytest

from auralis.library.sqlite_wal import enable_wal

LIBRARY_ROOT = Path(__file__).resolve().parents[3] / 'auralis'


def _locked_fresh_file(tmp_path: Path) -> sqlite3.Connection:
    """A rollback-journal file with another connection holding an exclusive lock."""
    # check_same_thread=False: the first test releases the lock from a timer thread.
    holder = sqlite3.connect(tmp_path / 'library.db', isolation_level=None, check_same_thread=False)
    holder.execute('CREATE TABLE t (x)')
    holder.execute('BEGIN EXCLUSIVE')
    return holder


def test_switch_waits_out_a_lock_the_busy_timeout_would_not(tmp_path):
    holder = _locked_fresh_file(tmp_path)
    conn = sqlite3.connect(tmp_path / 'library.db', timeout=0, isolation_level=None)

    with pytest.raises(sqlite3.OperationalError, match='database is locked'):
        conn.execute('PRAGMA journal_mode=WAL')

    release = threading.Timer(0.1, lambda: holder.execute('COMMIT'))
    release.start()
    try:
        enable_wal(conn.cursor(), timeout_s=5)
    finally:
        release.join()

    assert conn.execute('PRAGMA journal_mode').fetchone() == ('wal',)


def test_a_lock_that_outlasts_the_budget_still_raises(tmp_path):
    holder = _locked_fresh_file(tmp_path)
    conn = sqlite3.connect(tmp_path / 'library.db', timeout=0, isolation_level=None)
    try:
        with pytest.raises(sqlite3.OperationalError, match='database is locked'):
            enable_wal(conn.cursor(), timeout_s=0.05)
    finally:
        holder.execute('COMMIT')


def test_other_errors_are_not_retried():
    calls = []

    class Cursor:
        def execute(self, sql):
            calls.append(sql)
            raise sqlite3.OperationalError('disk I/O error')

    with pytest.raises(sqlite3.OperationalError, match='disk I/O error'):
        enable_wal(Cursor(), timeout_s=5)
    assert calls == ['PRAGMA journal_mode=WAL']


def test_no_engine_runs_the_bare_pragma():
    """Every connect hook goes through enable_wal(), not its own PRAGMA."""
    offenders = [
        str(path.relative_to(LIBRARY_ROOT.parent))
        for path in sorted(LIBRARY_ROOT.rglob('*.py'))
        if path.name != 'sqlite_wal.py' and 'journal_mode=WAL' in path.read_text(encoding='utf-8')
    ]
    assert offenders == []
