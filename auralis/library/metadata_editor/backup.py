"""
Backup Operations
~~~~~~~~~~~~~~~~~

File backup and restore operations for safe metadata editing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
import shutil
import tempfile
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from ...utils.logging import debug, error, info, warning

_file_locks_guard = threading.Lock()
# realpath -> (lock, number of threads holding or waiting on it). An entry is
# dropped once nobody uses it, so the registry does not grow with every file
# ever edited.
_file_locks: dict[str, tuple[threading.RLock, int]] = {}


@contextmanager
def lock_files(filepaths: Iterable[str]) -> Iterator[None]:
    """Hold an exclusive per-file lock on every path for the duration (#5307).

    Serializes metadata writes to the same file across the single-track and
    batch paths, so two requests cannot race on one file's backup or
    interleave their saves. Locks are re-entrant (``batch_update`` calls
    ``write_metadata`` while holding them) and taken in sorted-path order, so
    two batches over overlapping files cannot deadlock.
    """
    keys = sorted({os.path.realpath(p) for p in filepaths})
    locks: list[threading.RLock] = []
    with _file_locks_guard:
        for key in keys:
            lock, users = _file_locks.get(key) or (threading.RLock(), 0)
            _file_locks[key] = (lock, users + 1)
            locks.append(lock)

    acquired: list[threading.RLock] = []
    try:
        for lock in locks:
            lock.acquire()
            acquired.append(lock)
        yield
    finally:
        for lock in reversed(acquired):
            lock.release()
        with _file_locks_guard:
            for key in keys:
                lock, users = _file_locks[key]
                if users == 1:
                    del _file_locks[key]
                else:
                    _file_locks[key] = (lock, users - 1)


class BackupManager:
    """Manages file backups for safe metadata editing.

    Every backup is a unique hidden sibling of the file (#5307), never a fixed
    ``<file>.bak``: with a fixed name, a copy left over from an earlier,
    already-successful edit could be restored over a later one. Callers keep
    the path ``create_backup`` returns and hand it back to restore or clean
    up exactly that copy. Same directory, so restore is an atomic rename.
    """

    @staticmethod
    def create_backup(filepath: str) -> str | None:
        """
        Create backup of file before modification

        Args:
            filepath: Path to file to backup

        Returns:
            Path of the new backup copy, or None if it could not be created
        """
        directory, name = os.path.split(os.path.abspath(filepath))
        backup_path: str | None = None
        try:
            # Truncate the name so prefix + random part + suffix stays well
            # inside the filesystem's 255-byte filename limit.
            fd, backup_path = tempfile.mkstemp(
                prefix=f".{name[:64]}.", suffix='.bak', dir=directory
            )
            os.close(fd)
            shutil.copy2(filepath, backup_path)
            debug(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            warning(f"Failed to create backup of {filepath}: {e}")
            if backup_path is not None:
                BackupManager.cleanup_backup(backup_path)
            return None

    @staticmethod
    def restore_backup(filepath: str, backup_path: str) -> bool:
        """
        Restore file from the backup copy created for it

        Args:
            filepath: Path to original file
            backup_path: Path returned by ``create_backup`` for this file

        Returns:
            True if restored successfully, False otherwise (the backup is kept)
        """
        if not Path(backup_path).exists():
            error(f"Backup {backup_path} for {filepath} is missing; cannot restore")
            return False
        try:
            os.replace(backup_path, filepath)
            info(f"Restored from backup: {filepath}")
            return True
        except Exception as e:
            error(f"Failed to restore {filepath} from backup {backup_path} (backup kept): {e}")
            return False

    @staticmethod
    def cleanup_backup(backup_path: str) -> bool:
        """
        Remove a backup copy after a successful (or aborted) operation

        Args:
            backup_path: Path returned by ``create_backup``

        Returns:
            True if backup removed, False otherwise
        """
        try:
            Path(backup_path).unlink()
            debug(f"Removed backup: {backup_path}")
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            warning(f"Failed to remove backup {backup_path}: {e}")
            return False
