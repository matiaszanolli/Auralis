"""
Auralis Migration Lock
~~~~~~~~~~~~~~~~~~~~~~

Thread- *and* process-exclusive lock guarding schema migrations.

Split out of ``migration_manager.py`` (#4511); ``migration_manager`` re-exports
``migration_lock`` so existing imports keep working.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import platform
import threading
import time
from contextlib import contextmanager
from pathlib import Path

# Import platform-specific file locking
if platform.system() == "Windows":
    import msvcrt
else:
    import fcntl

logger = logging.getLogger(__name__)

__all__ = ['migration_lock']


# Serializes the migration step across threads IN THE SAME PROCESS (#4232).
# The file lock below is inter-*process* only: `fcntl.flock` is per open-file-
# description, so two threads sharing one process each open their own fd and
# both acquire it, and `msvcrt.locking` byte-range locks are per-process, so on
# Windows nothing serializes same-process threads at all.
#
# This lives here rather than at the caller (#4523) so BOTH entry points get it
# — `check_and_migrate_database` and `migrations.normalize_existing_artists`.
# It used to live in `LibraryDatabase.__init__`, which meant the second entry
# point had process serialization only. Global rather than per-path: migrations
# run at startup against a single database, and a global lock is strictly
# stronger than a per-path one.
_thread_lock = threading.Lock()


@contextmanager
def migration_lock(db_path: str, timeout: float = 30.0):
    """
    Acquire the migration lock: thread-exclusive *and* process-exclusive.

    Two layers are needed because neither covers the other's case — see the
    ``_thread_lock`` comment above. ``timeout`` is a budget shared across both
    acquisitions, not a per-layer allowance.

    The lock file is deliberately **never deleted** (#4523). ``flock``/
    ``msvcrt`` locks are bound to an *inode*, not a path, so unlinking it
    destroys the path→inode identity the lock is built on: a waiter still
    queued on the old (now unlinked, unreachable) inode and a fresh arrival
    that creates a brand-new inode would both believe they hold the lock. A
    zero-byte sentinel next to the database is the cheap price of correctness.

    Args:
        db_path: Path to database file
        timeout: Maximum total time to wait for the lock in seconds

    Yields:
        None (lock is held during context)

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
        OSError: If lock file cannot be created
    """
    db_path_obj = Path(db_path)
    lock_file = db_path_obj.parent / f".{db_path_obj.name}.migration.lock"

    # Ensure directory exists
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    deadline = time.monotonic() + timeout

    if not _thread_lock.acquire(timeout=timeout):
        raise TimeoutError(
            f"Could not acquire migration lock within {timeout}s. "
            "Another thread may be migrating the database."
        )

    lock_fd = None
    try:
        # Open lock file
        lock_fd = open(lock_file, 'w')

        if platform.system() == "Windows":
            # Windows: Use msvcrt.locking with retry loop
            while True:
                try:
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"Could not acquire migration lock within {timeout}s. "
                            "Another process may be migrating the database."
                        )
                    time.sleep(0.1)
        else:
            # Linux/macOS: Use fcntl.flock with timeout
            while True:
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"Could not acquire migration lock within {timeout}s. "
                            "Another process may be migrating the database."
                        )
                    time.sleep(0.1)

        logger.debug(f"Acquired migration lock: {lock_file}")
        yield

    finally:
        # Release lock. The lock FILE stays — see the docstring; unlinking it is
        # what #4523 is about.
        if lock_fd:
            try:
                if platform.system() == "Windows":
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
                logger.debug(f"Released migration lock: {lock_file}")
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")
        _thread_lock.release()
