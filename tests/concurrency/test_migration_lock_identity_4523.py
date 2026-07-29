"""
Migration lock identity and thread coverage (issue #4523)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two defects, one context manager:

1. ``migration_lock`` unlinked its own lock file on release. ``flock``/``msvcrt``
   locks are bound to an *inode*, not a path, so deleting the file destroys the
   path→inode identity the lock depends on. A waiter still queued on the old
   (now unreachable) inode and a fresh arrival that creates a brand-new inode
   both end up "holding" the lock.

2. The same-process thread lock lived in ``LibraryDatabase.__init__``, so the
   second migration entry point — ``migrations.normalize_existing_artists`` —
   had inter-process serialization only. On Windows, where ``msvcrt`` byte-range
   locks are per-process, that route serialized nothing at all.

True parallelism is exercised with ``multiprocessing.Process`` + ``Queue`` per
the project's concurrency-testing pattern.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import multiprocessing
import tempfile
import threading
import time
from pathlib import Path

import pytest

from auralis.library.migration_manager import migration_lock


def _lock_path(db_path: str) -> Path:
    p = Path(db_path)
    return p.parent / f".{p.name}.migration.lock"


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmp:
        yield str(Path(tmp) / "library.db")


# --- module-level workers: must be importable for the spawn start method ---

def _hold_and_report(db_path: str, hold_s: float, queue) -> None:
    """Acquire the lock, record the [enter, exit] interval, release."""
    try:
        with migration_lock(db_path, timeout=30.0):
            enter = time.time()
            time.sleep(hold_s)
            queue.put(("ok", enter, time.time()))
    except Exception as exc:  # pragma: no cover - surfaced via the queue
        queue.put(("error", repr(exc), 0.0))


def _record_inode(db_path: str, queue) -> None:
    """Report the lock file's inode as seen from a separate process."""
    try:
        with migration_lock(db_path, timeout=30.0):
            queue.put(("ok", _lock_path(db_path).stat().st_ino, 0.0))
    except Exception as exc:  # pragma: no cover
        queue.put(("error", repr(exc), 0.0))


class TestLockFilePersists:
    """The sentinel file is the lock's identity — it must never be unlinked."""

    def test_file_survives_release(self, temp_db):
        with migration_lock(temp_db):
            assert _lock_path(temp_db).exists()
        assert _lock_path(temp_db).exists()

    def test_inode_is_stable_across_acquisitions(self, temp_db):
        """The whole point: same path -> same inode, every time."""
        with migration_lock(temp_db):
            first = _lock_path(temp_db).stat().st_ino
        with migration_lock(temp_db):
            second = _lock_path(temp_db).stat().st_ino
        assert first == second, (
            "lock file was recreated between acquisitions — the path no longer "
            "identifies a single inode, so contenders can hold different ones"
        )

    def test_migration_lock_never_unlinks(self):
        """AST guard: no unlink() anywhere inside `migration_lock` itself.

        Scoped to the function, not the module — `restore_database` legitimately
        unlinks stale -wal/-shm sidecars and must not be caught here.
        """
        import ast

        import auralis.library.migration_manager as mm

        tree = ast.parse(Path(mm.__file__).read_text())
        (fn,) = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "migration_lock"
        ]
        unlinks = [
            node
            for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "unlink"
        ]
        assert not unlinks, f"migration_lock has {len(unlinks)} unlink() call(s)"


class TestThreadSerialization:
    """Both entry points must serialize same-process threads (#4232 gap)."""

    def test_two_threads_do_not_overlap(self, temp_db):
        inside = []
        max_concurrent = 0
        guard = threading.Lock()

        def worker():
            nonlocal max_concurrent
            with migration_lock(temp_db, timeout=30.0):
                with guard:
                    inside.append(1)
                    max_concurrent = max(max_concurrent, len(inside))
                time.sleep(0.15)
                with guard:
                    inside.pop()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert max_concurrent == 1, (
            f"{max_concurrent} threads held the migration lock at once"
        )

    def test_thread_contention_reports_a_timeout(self, temp_db):
        """A blocked thread raises TimeoutError rather than proceeding."""
        started = threading.Event()
        result: list[object] = []

        def holder():
            with migration_lock(temp_db, timeout=30.0):
                started.set()
                time.sleep(0.6)

        t = threading.Thread(target=holder)
        t.start()
        assert started.wait(timeout=10)

        try:
            with migration_lock(temp_db, timeout=0.2):
                result.append("acquired")
        except TimeoutError as exc:
            result.append(exc)
        finally:
            t.join(timeout=30)

        assert isinstance(result[0], TimeoutError), (
            "a second thread acquired the lock while it was held"
        )


@pytest.mark.slow
class TestProcessSerialization:
    """The A-releases-and-unlinks ordering must no longer let B and C overlap."""

    def test_three_processes_do_not_overlap(self, temp_db):
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()

        procs = [
            ctx.Process(target=_hold_and_report, args=(temp_db, 0.5, queue))
            for _ in range(3)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=90)

        intervals = []
        for _ in range(3):
            status, a, b = queue.get(timeout=30)
            assert status == "ok", f"worker failed: {a}"
            intervals.append((a, b))

        intervals.sort()
        for (_, prev_end), (next_start, _) in zip(intervals, intervals[1:]):
            assert next_start >= prev_end - 1e-6, (
                "two processes held the migration lock at overlapping times"
            )

    def test_second_process_sees_the_same_inode(self, temp_db):
        with migration_lock(temp_db):
            local_inode = _lock_path(temp_db).stat().st_ino

        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        p = ctx.Process(target=_record_inode, args=(temp_db, queue))
        p.start()
        p.join(timeout=90)

        status, remote_inode, _ = queue.get(timeout=30)
        assert status == "ok", f"worker failed: {remote_inode}"
        assert remote_inode == local_inode, (
            "a second process created a fresh inode for the same lock path"
        )
