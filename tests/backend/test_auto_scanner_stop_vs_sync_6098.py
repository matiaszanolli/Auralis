"""
Regression test: LibraryAutoScanner.stop() racing an in-flight _sync_watchdog
must not leave a watchdog Observer running (#6098).

_sync_watchdog awaits ``to_thread(_stop_watchdog)`` before building the new
Observer. stop() can complete its own teardown during that await; when the
sync then resumed it started an Observer nothing would ever stop.
"""

import asyncio
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.library_auto_scanner import LibraryAutoScanner


def _make_scanner() -> LibraryAutoScanner:
    settings = SimpleNamespace(auto_scan=True, scan_folders=json.dumps([]), scan_interval=3600)
    return LibraryAutoScanner(
        settings_repo=MagicMock(get_settings=MagicMock(return_value=settings)),
        library_database=MagicMock(),
        fingerprint_queue=None,
        connection_manager=MagicMock(),
    )


@pytest.mark.asyncio
async def test_stop_during_sync_watchdog_teardown_leaves_no_observer():
    scanner = _make_scanner()

    old_observer = MagicMock()
    old_observer.is_alive.return_value = True
    old_watch = MagicMock()
    old_watch.path = "/old"
    old_observer._watches = [old_watch]
    scanner._observer = old_observer

    started: list[MagicMock] = []

    def make_observer() -> MagicMock:
        observer = MagicMock()
        started.append(observer)
        return observer

    in_teardown = threading.Event()
    release_teardown = threading.Event()
    calls = 0

    def stop_watchdog() -> None:
        # The first caller is _sync_watchdog (folder list changed); hold it
        # inside the await so stop() overlaps it. stop()'s own call returns at once.
        nonlocal calls
        calls += 1
        if calls == 1:
            in_teardown.set()
            assert release_teardown.wait(timeout=5)
        scanner._observer = None

    with patch("services.scanner_watchdog.HAS_WATCHDOG", True), \
         patch("services.scanner_watchdog.Observer", side_effect=make_observer), \
         patch.object(scanner, "_stop_watchdog", side_effect=stop_watchdog):
        sync = asyncio.create_task(scanner._sync_watchdog(["/new"]))
        await asyncio.to_thread(in_teardown.wait, 5)

        await scanner.stop()
        release_teardown.set()
        await sync

    assert started == []
    assert scanner._observer is None


@pytest.mark.asyncio
async def test_sync_watchdog_still_starts_observer_when_not_stopping():
    scanner = _make_scanner()
    observer = MagicMock()

    with patch("services.scanner_watchdog.HAS_WATCHDOG", True), \
         patch("services.scanner_watchdog.Observer", return_value=observer):
        await scanner._sync_watchdog(["/new"])

    observer.start.assert_called_once()
    assert scanner._observer is observer
