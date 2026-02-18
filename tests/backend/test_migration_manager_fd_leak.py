"""
MigrationManager File-Descriptor Leak Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression guard for issue #2395:
  MigrationManager.__init__ creates a new SQLAlchemy engine on every call.
  The old close() only called session.close() -- the engine (and its connection
  pool) was never disposed, leaving open file descriptors to the SQLite file
  after every LibraryManager init.

Test plan from the issue:
  fd_before = len(os.listdir('/proc/self/fd'))
  Create and close 100 MigrationManagers
  assert len(os.listdir('/proc/self/fd')) == fd_before

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root so auralis imports resolve.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auralis.library.migration_manager import MigrationManager


# /proc/self/fd is Linux-only; skip on other platforms.
pytestmark = pytest.mark.skipif(
    not Path("/proc/self/fd").exists(),
    reason="/proc/self/fd not available on this platform"
)


class TestMigrationManagerFDLeak:
    """
    Verify that MigrationManager.close() releases all file descriptors
    owned by the SQLAlchemy engine (issue #2395).
    """

    def test_no_fd_leak_after_repeated_create_and_close(self, tmp_path):
        """
        Creating and closing 100 MigrationManagers must not grow the open-fd count.

        A leak would show up as /proc/self/fd entries accumulating because
        SQLite keeps the WAL / journal file descriptors open through the
        connection pool until engine.dispose() is called.
        """
        db_path = str(tmp_path / "test.db")

        # Warm up: one round to trigger any one-time internal allocations
        # (e.g. Python's own SQLite driver loading) so they don't skew the count.
        mm = MigrationManager(db_path)
        mm.close()

        fd_before = len(os.listdir("/proc/self/fd"))

        for _ in range(100):
            mm = MigrationManager(db_path)
            mm.close()

        fd_after = len(os.listdir("/proc/self/fd"))

        assert fd_after == fd_before, (
            f"File descriptor leak detected: {fd_after - fd_before} extra fd(s) "
            f"remain after creating and closing 100 MigrationManagers "
            f"(before={fd_before}, after={fd_after}). "
            "engine.dispose() must be called in MigrationManager.close() (issue #2395)."
        )

    def test_close_disposes_engine(self, tmp_path):
        """
        After close(), the engine pool must report zero checked-out connections.

        SQLAlchemy's StaticPool (used for SQLite) exposes the pool status via
        engine.pool; dispose() resets the pool to its initial state.
        """
        db_path = str(tmp_path / "test.db")
        mm = MigrationManager(db_path)

        # Touch the engine to ensure at least one connection was made.
        _ = mm.get_current_version()

        mm.close()

        # After dispose() the pool's checkedout counter must be 0.
        # pool.checkedout() is available on all SQLAlchemy pool implementations.
        assert mm.engine.pool.checkedout() == 0, (
            "Engine pool still has checked-out connections after close() — "
            "engine.dispose() was not called (issue #2395)."
        )
