"""
Engine and file-permission bootstrap for LibraryDatabase (split from
database.py, #5837): the pieces of ``__init__`` that touch the filesystem and
SQLite configuration but know nothing about repositories.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from ..utils.logging import info, warning
from .constants import DEFAULT_DB_PATH, SQLITE_BUSY_TIMEOUT_MS, SQLITE_CONNECT_TIMEOUT_S
from .models import Base
from .schema_indexes import create_missing_declared_indexes


def resolve_database_path(database_path: str | None) -> str:
    """Return the database path, hardening ``~/.auralis`` when it is the location."""
    # #4824: harden ~/.auralis whenever the database lives at the default
    # location, not only when the caller omitted the path. fetch_artwork.py
    # passes DEFAULT_DB_PATH explicitly, so it skipped this block and the
    # directory was created later by migration_lock's plain mkdir at the
    # process umask (typically 0o755). A caller-chosen location elsewhere
    # is deliberately left alone — that directory is not ours to chmod.
    if database_path is None or os.path.realpath(database_path) == os.path.realpath(DEFAULT_DB_PATH):
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # mkdir(mode=) is ignored when the dir already exists, so re-restrict
        # it to owner-only even for a pre-existing ~/.auralis (#4347).
        try:
            os.chmod(DEFAULT_DB_PATH.parent, 0o700)
        except OSError:
            pass
    if database_path is None:
        database_path = str(DEFAULT_DB_PATH)
    return database_path


def create_library_engine(database_path: str) -> Engine:
    """Create the engine with the WAL/pragma configuration the fingerprint writers rely on."""
    # Configure SQLite for safe, frequent fingerprint writes
    # WAL mode + synchronous=NORMAL enables fast writes with durability guarantees
    connect_args = {
        'timeout': SQLITE_CONNECT_TIMEOUT_S,  # WAL makes contention rare
        'check_same_thread': False,
    }

    # SQLite allows only one writer at a time. With WAL mode, readers don't
    # block writers (and vice versa), so a small pool is sufficient even under
    # heavy concurrent load. Sessions are short-lived (session-per-method),
    # so connections are returned quickly. (#2086)
    engine = create_engine(
        f"sqlite:///{database_path}",
        echo=False,
        connect_args=connect_args,
        pool_pre_ping=True,  # Verify connections before use
        pool_size=5,  # Sufficient for SQLite with WAL concurrent readers
        max_overflow=5,  # Up to 10 total connections
    )

    # Restrict database file permissions to owner-only (#2577)
    db_path = Path(database_path)
    if db_path.exists():
        try:
            os.chmod(db_path, 0o600)
        except OSError:
            pass

    # Configure SQLite pragmas for reliable fingerprinting persistence
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        """Set SQLite pragmas for safe, fast writes"""
        cursor = dbapi_connection.cursor()
        # Enable Write-Ahead Logging for better concurrent write performance
        cursor.execute("PRAGMA journal_mode=WAL")
        # Set synchronous to NORMAL (safer than OFF, faster than FULL)
        # Ensures fingerprints are durably written to WAL before returning
        cursor.execute("PRAGMA synchronous=NORMAL")
        # SQLite applies cache_size PER CONNECTION, not as an aggregate. With
        # pool_size=5 + max_overflow=5 (up to 10 connections), 8MB/connection
        # caps the worst-case aggregate at 80MB instead of 640MB. (#4779)
        cursor.execute("PRAGMA cache_size=-8192")  # 8MB cache per connection
        # Optimize for frequent writes
        cursor.execute("PRAGMA temp_store=MEMORY")
        # Foreign key enforcement for data integrity
        cursor.execute("PRAGMA foreign_keys=ON")
        # Increase max page count for larger working set
        cursor.execute("PRAGMA max_page_count=1073741823")  # ~4GB max database
        # Explicit busy timeout at PRAGMA level for consistent behavior (#2091)
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cursor.close()

    return engine


def create_schema(engine: Engine) -> None:
    """Create missing tables and declared indexes on ``engine``."""
    # Create tables if they don't exist (for fresh databases). This opens a
    # connection, which fires the connect event and switches the DB to WAL
    # mode — creating the -wal/-shm sidecars.
    Base.metadata.create_all(engine)

    # create_all() adds a table's indexes only when it creates the table, so
    # a database built before an index was declared would never get it
    # (#5321). An index is an optimization; never block startup on it.
    try:
        added_indexes = create_missing_declared_indexes(engine)
        if added_indexes:
            info(f"Created {len(added_indexes)} missing index(es): {', '.join(added_indexes)}")
    except Exception as e:  # noqa: BLE001
        warning(f"Declared-index repair skipped: {e}")


def restrict_wal_sidecars(database_path: str) -> None:
    """Make the WAL sidecars owner-only.

    SQLite creates them lazily with the process umask (often world/group-
    readable) and never chmods them, unlike the main DB. Restrict them so
    recently-played/library data isn't readable by other local accounts on a
    custom path or a pre-existing loose ~/.auralis (#4347).
    """
    for suffix in ("-wal", "-shm"):
        sidecar = Path(database_path + suffix)
        if sidecar.exists():
            try:
                os.chmod(sidecar, 0o600)
            except OSError:
                pass
