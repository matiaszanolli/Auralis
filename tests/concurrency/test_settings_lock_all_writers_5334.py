"""
Every writer of the singleton settings row shares one lock (issue #5334)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#4956 serialized ``add_scan_folder``/``remove_scan_folder`` with an in-process
lock, but the other paths that touch the same row — ``update_settings`` (the
PUT /api/settings route, which can carry ``scan_folders``), ``reset_to_defaults``
(which deletes the row) and ``get_settings``' default-row creation — took no
lock. They could overwrite a locked add/remove's edit or delete the row from
under it.

Each test parks an ``add_scan_folder`` inside its locked read and checks that
the other writer cannot finish until it is released. Real threads, per this
project's concurrency-testing pattern.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json
import threading

import pytest

WRITERS = {
    "update_settings": lambda repo: repo.update_settings({"scan_folders": ["/music/replaced"]}),
    "reset_to_defaults": lambda repo: repo.reset_to_defaults(),
    "get_settings": lambda repo: repo.get_settings(),
}


@pytest.fixture
def parked_add(settings_repository, monkeypatch):
    """Run an add_scan_folder that stops inside the locked section.

    Yields the event that lets it finish. The seed folder guarantees the
    locked read goes through json.loads, which is where it parks.
    """
    settings_repository.update_settings({"scan_folders": ["/music/seed"]})

    entered = threading.Event()
    release = threading.Event()
    real_loads = json.loads
    parked = False

    def parking_loads(data, *args, **kwargs):
        nonlocal parked
        if not parked:
            parked = True
            entered.set()
            release.wait(timeout=5)
        return real_loads(data, *args, **kwargs)

    monkeypatch.setattr(
        "auralis.library.repositories.settings_repository.json.loads", parking_loads
    )
    holder = threading.Thread(
        target=settings_repository.add_scan_folder, args=("/music/held",)
    )
    holder.start()
    assert entered.wait(timeout=5), "add_scan_folder never reached its locked read"

    yield release

    release.set()
    holder.join(timeout=5)


@pytest.mark.parametrize("writer", list(WRITERS.values()), ids=list(WRITERS))
def test_writer_waits_for_a_locked_scan_folder_edit(settings_repository, parked_add, writer):
    done = threading.Event()
    errors: list[BaseException] = []

    def run() -> None:
        try:
            writer(settings_repository)
        except BaseException as exc:  # pragma: no cover - surfaced via assert below
            errors.append(exc)
        finally:
            done.set()

    thread = threading.Thread(target=run)
    thread.start()

    assert not done.wait(timeout=0.5), "writer finished while add_scan_folder held the lock"

    parked_add.set()
    thread.join(timeout=5)
    assert done.is_set()
    assert not errors, f"writer raised: {errors}"


def test_update_after_a_locked_add_is_last_writer_wins(settings_repository, parked_add):
    """The PUT payload replaces the list the add committed, not a stale one."""
    thread = threading.Thread(
        target=settings_repository.update_settings,
        args=({"scan_folders": ["/music/replaced"]},),
    )
    thread.start()
    parked_add.set()
    thread.join(timeout=5)

    final = settings_repository.get_settings()
    assert json.loads(final.scan_folders) == ["/music/replaced"]


def test_concurrent_add_and_reset_never_raise(settings_repository):
    """reset_to_defaults deleting the row mid-add used to surface as a
    StaleDataError (a 500 from the settings routes)."""
    errors: list[BaseException] = []

    for round_number in range(10):
        barrier = threading.Barrier(4)

        def add(i: int) -> None:
            try:
                barrier.wait(timeout=5)
                settings_repository.add_scan_folder(f"/music/{round_number}_{i}")
            except BaseException as exc:  # pragma: no cover - surfaced via assert below
                errors.append(exc)

        def reset() -> None:
            try:
                barrier.wait(timeout=5)
                settings_repository.reset_to_defaults()
            except BaseException as exc:  # pragma: no cover - surfaced via assert below
                errors.append(exc)

        threads = [threading.Thread(target=add, args=(i,)) for i in range(3)]
        threads.append(threading.Thread(target=reset))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

    assert not errors, f"concurrent add/reset raised: {errors}"


def test_update_returns_the_folders_stored_before_it(settings_repository):
    """PUT /api/settings diffs its allowlist against this snapshot, so it has
    to come from the same locked transaction as the write."""
    settings_repository.update_settings({"scan_folders": ["/a", "/b"]})

    settings, previous = settings_repository.update_settings_with_previous_folders(
        {"scan_folders": ["/b", "/c"]}
    )

    assert previous == ["/a", "/b"]
    assert json.loads(settings.scan_folders) == ["/b", "/c"]


def test_update_without_scan_folders_reads_no_previous_list(settings_repository):
    settings_repository.update_settings({"scan_folders": ["/a"]})

    _settings, previous = settings_repository.update_settings_with_previous_folders(
        {"theme": "light"}
    )

    assert previous == []
