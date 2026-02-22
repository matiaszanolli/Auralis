"""
Test background library scan during startup

Tests the actual _background_auto_scan() function (not simulated patterns).
Validates that:
1. Scan runs in background without blocking server startup
2. Scan progress is broadcast via WebSocket
3. Errors are caught and broadcast, not silently swallowed
4. asyncio.to_thread() is used for the blocking scan call

Related: #2193 (tests were simulating patterns instead of testing production code)
         #2189 (asyncio.create_task from thread — fixed, verified by test_scan_progress_thread_safe.py)

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import _background_auto_scan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_connection_manager() -> MagicMock:
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    return manager


def _make_scanner(
    progress_calls: list[dict] | None = None,
    raise_exception: Exception | None = None,
) -> MagicMock:
    """
    Build a LibraryScanner mock whose scan_directories() fires the registered
    progress callback once per entry in progress_calls, then returns a result.
    Optionally raises an exception to test error handling.
    """
    scanner = MagicMock()
    _callback: list = []

    def set_cb(cb):
        _callback.append(cb)

    scanner.set_progress_callback.side_effect = set_cb

    def run_scan(directories, recursive=True, skip_existing=True):
        if raise_exception:
            raise raise_exception

        for data in (progress_calls or []):
            if _callback:
                _callback[0](data)

        result = MagicMock()
        result.files_added = len(progress_calls or [])
        result.files_found = len(progress_calls or [])
        result.files_processed = len(progress_calls or [])
        result.scan_time = 0.01
        return result

    scanner.scan_directories.side_effect = run_scan
    return scanner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_background_scan_does_not_block():
    """
    _background_auto_scan() must be schedulable as a background task that
    completes asynchronously without blocking the caller.

    Previously, tests simulated their own scan coroutine. This test calls the
    real function and verifies that asyncio.create_task() returns immediately
    while the scan completes in the background (fixes #2193).
    """
    manager = _make_connection_manager()

    # Slow scanner — takes 100 ms
    scanner = _make_scanner()
    real_scan = scanner.scan_directories.side_effect

    def slow_scan(directories, recursive=True, skip_existing=True):
        import time as _time
        _time.sleep(0.1)
        return real_scan(directories, recursive=recursive, skip_existing=skip_existing)

    scanner.scan_directories.side_effect = slow_scan

    with patch("auralis.library.scanner.LibraryScanner", return_value=scanner):
        start = time.monotonic()
        # Schedule as a background task (as startup.py does)
        task = asyncio.create_task(
            _background_auto_scan(
                music_source_dir=Path("/fake/music"),
                library_manager=MagicMock(),
                fingerprint_queue=None,
                connection_manager=manager,
            )
        )
        scheduling_duration = time.monotonic() - start

        # create_task returns almost immediately — generous bound for loaded CI
        assert scheduling_duration < 0.5, (
            f"Scheduling took {scheduling_duration:.3f}s — scan must not block caller"
        )

        # The task should not be done yet since the scan takes 100ms
        assert not task.done(), "Task completed synchronously — scan must run in background"

        # Let the background task finish
        await task

    # Verify the scan actually ran
    scanner.scan_directories.assert_called_once()


@pytest.mark.asyncio
async def test_background_scan_broadcasts_websocket_events():
    """
    _background_auto_scan() must broadcast library_scan_started, scan_progress
    (once per progress callback), and scan_complete via the connection manager.

    Previously, tests used a local simulated_background_scan() that never
    exercised the real code path (fixes #2193).
    """
    manager = _make_connection_manager()
    progress_data = [
        {"processed": 5,   "total_found": 20, "progress": 0.25},
        {"processed": 10,  "total_found": 20, "progress": 0.50},
        {"processed": 20,  "total_found": 20, "progress": 1.00},
    ]
    scanner = _make_scanner(progress_data)

    with patch("auralis.library.scanner.LibraryScanner", return_value=scanner):
        await _background_auto_scan(
            music_source_dir=Path("/fake/music"),
            library_manager=MagicMock(),
            fingerprint_queue=None,
            connection_manager=manager,
        )

    # Allow any call_soon_threadsafe-scheduled tasks to flush
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    all_calls = [c.args[0] for c in manager.broadcast.call_args_list]
    event_types = [c.get("type") for c in all_calls]

    assert "library_scan_started" in event_types, "scan_started must be broadcast"
    assert "scan_complete" in event_types, "scan_complete must be broadcast"

    progress_events = [c for c in all_calls if c.get("type") == "scan_progress"]
    assert len(progress_events) == 3, (
        f"Expected 3 scan_progress events, got {len(progress_events)}"
    )

    # Verify scan_complete includes result data
    complete = next(c for c in all_calls if c.get("type") == "scan_complete")
    assert "data" in complete
    assert "tracks_added" in complete["data"]


@pytest.mark.asyncio
async def test_background_scan_error_handling():
    """
    Exceptions from scan_directories must be caught and broadcast as a
    library_scan_error message — the function must not propagate exceptions.

    Previously, tests used a local simulated_scan_with_error() that never
    tested the real try/except in _background_auto_scan (fixes #2193).
    """
    manager = _make_connection_manager()
    scanner = _make_scanner(raise_exception=RuntimeError("disk full"))

    with patch("auralis.library.scanner.LibraryScanner", return_value=scanner):
        # Must complete without raising
        await _background_auto_scan(
            music_source_dir=Path("/fake/music"),
            library_manager=MagicMock(),
            fingerprint_queue=None,
            connection_manager=manager,
        )

    all_calls = [c.args[0] for c in manager.broadcast.call_args_list]
    error_events = [c for c in all_calls if c.get("type") == "library_scan_error"]

    assert len(error_events) == 1, (
        f"Expected exactly one library_scan_error event, got {len(error_events)}"
    )
    assert "disk full" in error_events[0]["error"], (
        "Error message must be included in the broadcast"
    )


@pytest.mark.asyncio
async def test_asyncio_to_thread_used_for_scan():
    """
    scan_directories() must be called via asyncio.to_thread(), not directly,
    to avoid blocking the event loop.

    Previously, tests called asyncio.to_thread() themselves and verified the
    pattern in isolation instead of verifying the production call (fixes #2193).
    """
    manager = _make_connection_manager()
    scanner = _make_scanner()

    thread_funcs: list[object] = []
    real_to_thread = asyncio.to_thread

    async def spy_to_thread(func, *args, **kwargs):
        thread_funcs.append(func)
        return await real_to_thread(func, *args, **kwargs)

    with (
        patch("auralis.library.scanner.LibraryScanner", return_value=scanner),
        patch("asyncio.to_thread", side_effect=spy_to_thread),
    ):
        await _background_auto_scan(
            music_source_dir=Path("/fake/music"),
            library_manager=MagicMock(),
            fingerprint_queue=None,
            connection_manager=manager,
        )

    assert scanner.scan_directories in thread_funcs, (
        "scanner.scan_directories must be called via asyncio.to_thread() "
        "to avoid blocking the event loop (fixes #2193)"
    )
