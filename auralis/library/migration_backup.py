"""
Auralis Database Backup / Restore
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-migration safety net: consistent snapshots via the SQLite Online Backup
API, plus the matching restore path.

Split out of ``migration_manager.py`` (#4511); ``migration_manager`` re-exports
both functions so existing imports keep working.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ['backup_database', 'restore_database']


def backup_database(db_path: str, backup_dir: str | None = None) -> str:
    """
    Create a backup of the database file.

    Args:
        db_path: Path to database file
        backup_dir: Optional directory for backups (defaults to same dir as db)

    Returns:
        Path to the backup file
    """
    db_path_obj = Path(db_path)

    if not db_path_obj.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    # Determine backup directory
    if backup_dir:
        backup_path = Path(backup_dir)
    else:
        backup_path = db_path_obj.parent

    backup_path.mkdir(parents=True, exist_ok=True)

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_path / f"{db_path_obj.stem}.backup_{timestamp}{db_path_obj.suffix}"

    # Use sqlite3.Connection.backup() (SQLite Online Backup API) instead of
    # shutil.copy2().  shutil.copy2 copies only the .db file and silently
    # misses pages that are committed but not yet checkpointed into the main
    # file (i.e. data sitting in the -wal file).  sqlite3.backup() reads
    # through both the main file and the WAL, producing a fully consistent
    # point-in-time snapshot of all committed data.
    with sqlite3.connect(str(db_path_obj)) as src:
        with sqlite3.connect(str(backup_file)) as dst:
            src.backup(dst)

    # Absolute path embeds OS username + install layout (#4351/#4366); keep
    # the event at INFO but the path itself at DEBUG only (#4929).
    logger.info("✅ Database backed up")
    logger.debug(f"Backup location: {backup_file}")
    return str(backup_file)


def restore_database(backup_path: str, db_path: str) -> bool:
    """
    Restore database from backup using the SQLite Online Backup API.

    Uses sqlite3.Connection.backup() instead of shutil.copy2 to avoid
    WAL corruption: the backup API reads through the WAL and produces a
    consistent snapshot, and the restored file starts in rollback-journal
    mode so no stale -wal/-shm files can interfere (fixes #3452).

    Args:
        backup_path: Path to backup file
        db_path: Path to database file to restore

    Returns:
        True if successful
    """
    backup_path_obj = Path(backup_path)
    db_path_obj = Path(db_path)

    if not backup_path_obj.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    try:
        # Remove stale WAL/SHM sidecar files from the target before restoring.
        # If these files persist from a prior session they can cause the newly
        # restored database to open with an inconsistent WAL state.
        for suffix in ('-wal', '-shm'):
            sidecar = db_path_obj.with_suffix(db_path_obj.suffix + suffix)
            if sidecar.exists():
                sidecar.unlink()

        # Use SQLite Online Backup API (same as backup_database) to restore.
        # This reads through the backup's WAL (if any) and writes a fully
        # consistent main database file.
        with sqlite3.connect(str(backup_path_obj)) as src:
            with sqlite3.connect(str(db_path_obj)) as dst:
                src.backup(dst)

        # Path stays at DEBUG only — see backup_database's rationale (#4929).
        logger.info("✅ Database restored")
        logger.debug(f"Restored from: {backup_path}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to restore database: {e}")
        return False
