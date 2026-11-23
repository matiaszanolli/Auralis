"""
Switching a SQLite connection to WAL journaling, retried on lock contention.

Every engine that opens the library file runs ``PRAGMA journal_mode=WAL`` in
its connect hook. On an established library that is a no-op, because WAL mode
is persistent. On a file that is still in rollback-journal mode, which is any
freshly created library until its first connection switches it, the switch
needs an exclusive lock, and SQLite returns "database is locked" immediately,
without consulting the busy timeout, when waiting could deadlock: this
connection holds the shared lock it took to read the header while another
connection is escalating to write. Ten threads opening a new library together
(tests/backend/test_concurrent_operations.py::test_concurrent_connection_cleanup)
hit that ~3% of the time, and LibraryDatabase raised MigrationError. The other
side finishes in milliseconds, so a short bounded retry resolves it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sqlite3
import time
from typing import Any

from .constants import SQLITE_CONNECT_TIMEOUT_S

__all__ = ['enable_wal']

_FIRST_RETRY_DELAY_S = 0.005
_MAX_RETRY_DELAY_S = 0.2


def enable_wal(cursor: Any, timeout_s: float = SQLITE_CONNECT_TIMEOUT_S) -> None:
    """Run ``PRAGMA journal_mode=WAL`` on ``cursor``, retrying "database is locked".

    Retries with exponential backoff (5 ms doubling to 200 ms) for up to
    ``timeout_s``, the same budget a connection gets to open. Any other error,
    or a lock that outlasts the budget, is raised as before.
    """
    deadline = time.monotonic() + timeout_s
    delay = _FIRST_RETRY_DELAY_S
    while True:
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError as e:
            if "database is locked" not in str(e) or time.monotonic() >= deadline:
                raise
        time.sleep(delay)
        delay = min(delay * 2, _MAX_RETRY_DELAY_S)
