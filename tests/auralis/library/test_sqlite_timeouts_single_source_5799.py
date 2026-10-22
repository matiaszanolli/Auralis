"""
Every engine on library.db shares one lock-wait policy (#5799).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

LibraryDatabase, the migration engine and FingerprintService's own engine each
typed ``PRAGMA busy_timeout=60000`` and a 15 s driver timeout. They are three
connections to one SQLite file, so the one with the shortest wait is the one
that raises "database is locked" under contention. The values now live in
``auralis/library/constants.py``; this opens all three engines and reads the
setting back from SQLite itself.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.analysis.fingerprint.fingerprint_service import _make_engine
from auralis.library.constants import SQLITE_BUSY_TIMEOUT_MS, SQLITE_CONNECT_TIMEOUT_S
from auralis.library.database import LibraryDatabase
from auralis.library.migration_engine import create_migration_engine


def _busy_timeout(engine):
    with engine.connect() as conn:
        return conn.exec_driver_sql("PRAGMA busy_timeout").scalar()


def test_all_three_engines_apply_the_shared_busy_timeout(tmp_path):
    db_path = tmp_path / "library.db"
    library = LibraryDatabase(str(db_path))
    try:
        engines = {
            "LibraryDatabase": library.engine,
            "migration": create_migration_engine(db_path),
            "fingerprint": _make_engine(db_path),
        }
        for name, engine in engines.items():
            assert _busy_timeout(engine) == SQLITE_BUSY_TIMEOUT_MS, name
    finally:
        library.shutdown()


def test_the_constants_keep_their_documented_units():
    # PRAGMA busy_timeout is milliseconds; the driver timeout is seconds. Mixing
    # them up turns a 60 s wait into 60 ms or 4 hours.
    assert SQLITE_BUSY_TIMEOUT_MS >= 1000
    assert 1 <= SQLITE_CONNECT_TIMEOUT_S <= 120
