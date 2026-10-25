"""
Auralis Library Database
~~~~~~~~~~~~~~~~~~~~~~~~

Owns the SQLite database itself: migration, engine, pragmas, session factory,
file-permission hardening, scan-slot accounting and orderly shutdown. Hands out
repositories through a :class:`RepositoryFactory`.

This is the composition root: the bootstrap responsibilities above live here,
and ``RepositoryFactory`` (which only takes a ready-made session factory) builds
the repositories on top of it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import atexit
import threading

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from ..utils.logging import error, info, warning
from .database_accessors import RepositoryAccessorsMixin
from .database_engine import (
    create_library_engine,
    create_schema,
    resolve_database_path,
    restrict_wal_sidecars,
)
from .migration_manager import MigrationError, check_and_migrate_database
from .repositories import RepositoryFactory
from .scan_coordinator import ScanCoordinator

# #4523: the same-process thread lock that used to live here (#4232) moved into
# `migration_manager.migration_lock`, which now acquires thread *and* process
# exclusion together. Do not re-add a thread lock here: holding a second lock
# in this constructor would deadlock against it, and any entry point that
# bypasses this constructor would be left unserialized anyway.


class LibraryDatabase(RepositoryAccessorsMixin):
    """
    The library's SQLite database and everything needed to talk to it.

    Responsibilities:
    - Run pending schema migrations exactly once, under a process-wide lock
    - Create the engine with the WAL/pragma configuration the fingerprint
      writers depend on
    - Restrict the DB file and its WAL sidecars to owner-only (#2577, #4347)
    - Expose repositories via :attr:`repositories` (a ``RepositoryFactory``)
    - Account for concurrent scan slots (#2438)
    - Checkpoint the WAL and dispose the pool on shutdown (#2066)

    Example:
        ```python
        db = LibraryDatabase()
        tracks, total = db.repositories.tracks.get_all(limit=50)
        ```

    The repository accessors (:attr:`tracks`, :attr:`albums`, …) are
    conveniences that forward to :attr:`repositories`; they exist so components
    that only need one repository can take this object and reach it directly.
    """

    def __init__(self, database_path: str | None = None) -> None:
        """
        Open (migrating if needed) the library database.

        Args:
            database_path: Path to the SQLite database file. Defaults to
                ``~/.auralis/library.db``.

        Raises:
            MigrationError: If the schema migration fails — the caller must not
                proceed against a half-migrated database.
        """
        database_path = resolve_database_path(database_path)
        self.database_path = database_path

        # Check and migrate database before initializing engine. `migration_lock`
        # (in migration_manager) now serializes both same-process threads and
        # other processes (#4232, #4523), so no additional lock is needed here.
        info("Checking database version...")
        if not check_and_migrate_database(database_path, auto_backup=True):
            error("Database migration failed!")
            raise MigrationError("Failed to migrate database to current version")

        # `Engine | None` because shutdown() clears it (#3769) — __del__ gates
        # its own shutdown attempt on the None.
        self.engine: Engine | None = create_library_engine(database_path)
        self.SessionLocal = sessionmaker(self.engine)
        create_schema(self.engine)
        restrict_wal_sidecars(database_path)

        # Single source of repositories. Everything that needs the DB goes
        # through here — no component builds its own factory off SessionLocal.
        self.repositories = RepositoryFactory(self.SessionLocal)

        # #4842: the v017->v018 migration adds tracks.filepath_key but cannot
        # fill it — the key is case-folded only on case-insensitive platforms,
        # and SQLite's ASCII-only lower() disagrees with str.casefold() on the
        # non-ASCII paths a music library is full of. Fill it here, where
        # make_filepath_key() is available and remains the single authority.
        # Idempotent: matches nothing on every start after the first.
        try:
            self.repositories.tracks.backfill_filepath_keys()
        except Exception as e:  # noqa: BLE001 - never block startup on a backfill
            warning(f"filepath_key backfill skipped: {e}")

        # Thread-safe locking for delete operations (prevents race conditions)
        self._delete_lock = threading.RLock()

        # Scan slots, per-directory dedup and destructive-operation exclusion
        # live on one coordinator (#2438, #3455, #4509, #4816). It must hang off
        # this object, not LibraryScanner: every caller constructs a FRESH
        # scanner per invocation, and this is the one thing they share.
        self._scans = ScanCoordinator(lambda: self.settings.get_settings())

        # Clean up incomplete fingerprints from interrupted sessions (crash recovery)
        self._cleanup_incomplete_fingerprints()

        # Register cleanup handler for graceful shutdown (#2066)
        atexit.register(self.shutdown)

        info(f"Auralis library database opened: {database_path}")

    # ------------------------------------------------------------------
    # Scan concurrency (#2438) -- state lives on ScanCoordinator
    # ------------------------------------------------------------------

    def try_acquire_scan_slot(self) -> tuple[bool, int]:
        """Atomically reserve a concurrent scan slot; see :class:`ScanCoordinator`."""
        return self._scans.try_acquire_scan_slot()

    def release_scan_slot(self) -> None:
        """Release a slot previously acquired by :meth:`try_acquire_scan_slot`."""
        self._scans.release_scan_slot()

    def try_reserve_scan_paths(self, paths: list[str]) -> list[str]:
        """Reserve directories for a scan; returns the ones already reserved."""
        return self._scans.try_reserve_scan_paths(paths)

    def release_scan_paths(self, paths: list[str]) -> None:
        """Release paths reserved by :meth:`try_reserve_scan_paths`."""
        self._scans.release_scan_paths(paths)

    def try_begin_exclusive_access(self) -> bool:
        """Reserve the library for a destructive operation (#4816)."""
        return self._scans.try_begin_exclusive_access()

    def end_exclusive_access(self) -> None:
        """Release exclusive access taken by :meth:`try_begin_exclusive_access`."""
        self._scans.end_exclusive_access()

    def is_scanning(self) -> bool:
        """True if at least one scan currently holds a slot (#4821)."""
        return self._scans.is_scanning()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """
        Release all database resources.

        Performs critical cleanup operations:
        1. WAL checkpoint (TRUNCATE) - flush WAL to main database file
        2. PRAGMA optimize - save query planner statistics
        3. Connection pool disposal - close all open connections

        This prevents WAL file corruption, leftover lockfiles, and lost
        uncommitted transactions.

        Automatically called via atexit on normal shutdown; safe to call
        manually and safe to call twice.

        Fixes #2066 - No resource cleanup on shutdown
        """
        if not hasattr(self, 'engine') or self.engine is None:
            return  # Already shut down or never initialized

        try:
            info("🛑 Shutting down library database...")

            # 1. Checkpoint WAL to ensure all data is in main database file
            with self.engine.connect() as conn:
                try:
                    # TRUNCATE mode: checkpoint and delete WAL/SHM files
                    result = conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
                    checkpoint_result = result.fetchone()
                    if checkpoint_result:
                        info(f"WAL checkpoint completed: {checkpoint_result}")
                except Exception as e:
                    error(f"WAL checkpoint failed: {e}")

                # 2. Optimize query planner statistics
                try:
                    conn.execute(text("PRAGMA optimize"))
                    info("Query planner optimized")
                except Exception as e:
                    error(f"PRAGMA optimize failed: {e}")

            # 3. Dispose connection pool (closes all connections)
            self.engine.dispose()
            info("Connection pool disposed")

            info("✅ Library database shutdown complete")

        except Exception as e:
            error(f"Error during library database shutdown: {e}")
        finally:
            # #3769: clear the engine reference in `finally` so a raise
            # from `engine.dispose()` (or the PRAGMA path above it)
            # doesn't leave a stale handle around. `__del__` checks
            # `self.engine is None` to gate its shutdown attempt, so a
            # stale handle meant `__del__` re-invoked shutdown from GC
            # — where loggers may already be torn down.
            self.engine = None

    def __del__(self) -> None:
        """
        Destructor - cleanup when object is garbage collected.

        Fallback cleanup in case the atexit handler doesn't run or the
        object is destroyed before application exit.
        """
        try:
            self.shutdown()
        except Exception:
            pass  # Suppress errors during garbage collection

    def _cleanup_incomplete_fingerprints(self) -> None:
        """
        Clean up incomplete fingerprints from interrupted fingerprinting sessions.

        When workers claim tracks, they create placeholder fingerprints (with LUFS=-100)
        to prevent race conditions. If the system crashes before processing completes,
        these placeholders remain in the database and must be cleaned up on restart
        so those tracks can be re-processed.

        This is CRITICAL for resumable large-scale fingerprinting jobs.
        """
        try:
            count = self.fingerprint_stats.cleanup_incomplete_fingerprints()

            if count > 0:
                warning(
                    f"Cleaned up {count} incomplete fingerprints from "
                    f"interrupted session. These tracks will be re-processed."
                )
            else:
                info("No incomplete fingerprints found - resuming clean session")

        except Exception as e:
            error(f"Error cleaning up incomplete fingerprints: {e}")
