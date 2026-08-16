"""
Auralis Migration Engine Factory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The SQLAlchemy engine (and its SQLite PRAGMA setup) used by
``MigrationManager``.

Split out of ``MigrationManager.__init__`` (#4511). The connect args and
PRAGMAs are unchanged — they deliberately mirror ``LibraryDatabase``'s engine
contract.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

__all__ = ['create_migration_engine']


def create_migration_engine(db_path: Path) -> Engine:
    """
    Create the migration engine for a SQLite database file.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        A configured SQLAlchemy Engine
    """
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={
            'timeout': 15,          # 15s busy timeout matches LibraryDatabase
            'check_same_thread': False,
        },
        # #3702: verify connection before use to avoid stale-connection
        # OperationalError when another process has checkpointed the
        # WAL between MigrationManager init and first use. Matches
        # LibraryDatabase's create_engine() contract.
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        # Explicit busy timeout at PRAGMA level for consistent behavior
        # under concurrent migration access (#3312, matches LibraryDatabase #2091).
        cursor.execute("PRAGMA busy_timeout=60000")  # 60s
        cursor.close()

    return engine
