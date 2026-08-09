"""
add_scan_folder/remove_scan_folder concurrency regression (issue #4956)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``select(UserSettings).with_for_update()`` compiled to a no-op on SQLite —
SQLAlchemy's SQLite dialect silently drops the ``FOR UPDATE`` clause, so the
fix shipped for #3339 never actually closed the read-modify-write race it
claimed to. #4956 replaces it with an in-process ``threading.RLock`` shared
by ``SettingsRepository.add_scan_folder``/``remove_scan_folder``.

True parallelism is exercised with real ``threading.Thread`` workers, per
this project's established concurrency-testing pattern.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
import threading
import time

import pytest
from sqlalchemy import select

from auralis.library.models import UserSettings
from auralis.library.repositories.settings_repository import SettingsRepository


def test_concurrent_add_scan_folder_loses_no_edit(settings_repository):
    """Two threads adding different folders at nearly the same time must
    both end up in the final list — this is exactly what the SQLite no-op
    used to lose (second commit silently overwrote the first's addition).
    """
    n_threads = 8
    barrier = threading.Barrier(n_threads)
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            barrier.wait(timeout=5)
            settings_repository.add_scan_folder(f"/music/folder_{i}")
        except BaseException as exc:  # pragma: no cover - surfaced via assert below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"worker threads raised: {errors}"

    final = settings_repository.get_settings()
    folders = json.loads(final.scan_folders) if final.scan_folders else []
    expected = {f"/music/folder_{i}" for i in range(n_threads)}
    assert expected.issubset(set(folders)), (
        f"lost concurrent add_scan_folder edits: expected {expected}, got {set(folders)}"
    )


def test_scan_folders_lock_actually_serializes(settings_repository, monkeypatch):
    """Verify the lock blocks a second writer's read until the first
    writer's mutate-and-commit finishes, not just "look" atomic.
    """
    order: list[str] = []
    release_first = threading.Event()

    real_json_loads = json.loads

    def slow_loads(data):
        result = real_json_loads(data)
        if not slow_loads.done:
            slow_loads.done = True
            order.append("first-read")
            # Hold the lock open long enough for the second thread to prove
            # it is blocked, not merely racing.
            release_first.wait(timeout=5)
        return result

    slow_loads.done = False
    monkeypatch.setattr(
        "auralis.library.repositories.settings_repository.json.loads", slow_loads
    )

    def first() -> None:
        settings_repository.add_scan_folder("/music/first")

    def second() -> None:
        # Give `first` a head start so it acquires the lock first.
        time.sleep(0.2)
        order.append("second-blocked-start")
        settings_repository.add_scan_folder("/music/second")
        order.append("second-done")

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    t2.start()

    # `second` must not be able to finish while `first` is still parked
    # inside the locked section.
    time.sleep(0.5)
    assert "second-done" not in order, "second writer ran while lock was held"

    release_first.set()
    t1.join(timeout=5)
    t2.join(timeout=5)

    # `first-read` (entering the locked section) must precede `second-done`
    # (the second writer completing) — the scheduling of `second-blocked-start`
    # relative to `first-read` is not itself under lock and isn't asserted.
    assert order.index("first-read") < order.index("second-done")
    assert order[-1] == "second-done"

    final = settings_repository.get_settings()
    folders = json.loads(final.scan_folders) if final.scan_folders else []
    assert "/music/first" in folders
    assert "/music/second" in folders


def test_with_for_update_compiles_to_no_op_on_sqlite(session_factory):
    """Documents the root cause: `with_for_update()` drops the `FOR UPDATE`
    clause entirely when compiled against SQLite — this is *why* the lock
    fix in #4956 is needed rather than relying on the ORM construct.
    """
    session = session_factory()
    try:
        stmt = select(UserSettings).with_for_update()
        compiled = str(stmt.compile(session.get_bind()))
        assert "FOR UPDATE" not in compiled.upper()
    finally:
        session.close()
