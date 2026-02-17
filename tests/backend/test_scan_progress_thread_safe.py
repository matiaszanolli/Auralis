"""
Test: sync_progress_callback uses call_soon_threadsafe in _background_auto_scan (fixes #2189)

Verifies that:
- sync_progress_callback() is safe to call from a background thread
- No RuntimeError: no running event loop is raised during scan progress
- Progress broadcasts are actually delivered to the connection manager
- _background_auto_scan() is tested directly, not via simulated patterns (#2193)
"""

import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup import _background_auto_scan


def _make_connection_manager() -> MagicMock:
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    return manager


def _make_scanner(progress_calls: list[dict]) -> MagicMock:
    """
    Return a scanner mock whose scan_directories() fires the registered
    progress callback once per entry in progress_calls, then returns a result.
    """
    scanner = MagicMock()
    scanner_callback: list = []

    def set_cb(cb):
        scanner_callback.append(cb)

    scanner.set_progress_callback.side_effect = set_cb

    def run_scan(directories, recursive=True, skip_existing=True):
        for data in progress_calls:
            if scanner_callback:
                scanner_callback[0](data)
        result = MagicMock()
        result.files_added = len(progress_calls)
        result.files_found = len(progress_calls)
        result.files_processed = len(progress_calls)
        result.scan_time = 0.1
        return result

    scanner.scan_directories.side_effect = run_scan
    return scanner


@pytest.mark.asyncio
async def test_progress_callback_safe_from_thread():
    """
    Calling sync_progress_callback from a background thread must not raise
    RuntimeError: no running event loop (the core regression for #2189).
    """
    manager = _make_connection_manager()
    progress_data = [{"processed": 1, "total_found": 10, "progress": 0.1}]
    scanner = _make_scanner(progress_data)

    errors: list[Exception] = []

    real_scan_directories = scanner.scan_directories.side_effect

    def scan_in_thread(directories, recursive, skip_existing):
        """Simulate what asyncio.to_thread does — runs in thread pool."""
        try:
            return real_scan_directories(directories, recursive=recursive,
                                         skip_existing=skip_existing)
        except Exception as e:
            errors.append(e)
            raise

    scanner.scan_directories.side_effect = scan_in_thread

    with (
        patch("auralis.library.scanner.LibraryScanner", return_value=scanner),
    ):
        await _background_auto_scan(
            music_source_dir=Path("/fake/music"),
            library_manager=MagicMock(),
            fingerprint_queue=None,
            connection_manager=manager,
        )

    assert not errors, (
        f"Exception raised in scanner thread (RuntimeError expected for #2189 if unfixed): {errors}"
    )


@pytest.mark.asyncio
async def test_progress_broadcasts_delivered():
    """
    Progress broadcasts must reach the connection manager even though they
    originate from a background thread via call_soon_threadsafe().
    """
    manager = _make_connection_manager()
    progress_data = [
        {"processed": 5, "total_found": 20, "progress": 0.25},
        {"processed": 10, "total_found": 20, "progress": 0.5},
        {"processed": 20, "total_found": 20, "progress": 1.0},
    ]
    scanner = _make_scanner(progress_data)

    with patch("auralis.library.scanner.LibraryScanner", return_value=scanner):
        await _background_auto_scan(
            music_source_dir=Path("/fake/music"),
            library_manager=MagicMock(),
            fingerprint_queue=None,
            connection_manager=manager,
        )

    # Give any pending call_soon_threadsafe tasks a chance to execute
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    all_calls = [call.args[0] for call in manager.broadcast.call_args_list]
    scan_progress_calls = [c for c in all_calls if c.get("type") == "scan_progress"]

    assert len(scan_progress_calls) == 3, (
        f"Expected 3 scan_progress broadcasts, got {len(scan_progress_calls)}. "
        "Progress callbacks from background thread were not delivered (bug #2189)."
    )


@pytest.mark.asyncio
async def test_call_soon_threadsafe_used_not_create_task():
    """
    sync_progress_callback must use loop.call_soon_threadsafe() rather than
    asyncio.create_task() directly, which would fail on a worker thread.
    """
    manager = _make_connection_manager()
    progress_data = [{"processed": 1, "total_found": 5, "progress": 0.2}]
    scanner = _make_scanner(progress_data)

    create_task_calls_from_thread: list[bool] = []
    threadsafe_calls: list[bool] = []

    loop = asyncio.get_running_loop()
    real_call_soon_threadsafe = loop.call_soon_threadsafe

    def spy_call_soon_threadsafe(callback, *args, **kwargs):
        # Record that call_soon_threadsafe was used
        threadsafe_calls.append(True)
        return real_call_soon_threadsafe(callback, *args, **kwargs)

    original_create_task = asyncio.create_task

    def spy_create_task(coro, **kwargs):
        # Record if create_task is called directly (the bug)
        current_thread = threading.current_thread()
        if current_thread is not threading.main_thread():
            create_task_calls_from_thread.append(True)
        return original_create_task(coro, **kwargs)

    with (
        patch("auralis.library.scanner.LibraryScanner", return_value=scanner),
        patch.object(loop, "call_soon_threadsafe", side_effect=spy_call_soon_threadsafe),
        patch("asyncio.create_task", side_effect=spy_create_task),
    ):
        await _background_auto_scan(
            music_source_dir=Path("/fake/music"),
            library_manager=MagicMock(),
            fingerprint_queue=None,
            connection_manager=manager,
        )

    assert not create_task_calls_from_thread, (
        "asyncio.create_task() was called directly from a background thread — "
        "bug #2189 is still present! Use loop.call_soon_threadsafe() instead."
    )
    assert threadsafe_calls, (
        "loop.call_soon_threadsafe() was never called — fix #2189 not applied."
    )


@pytest.mark.asyncio
async def test_scan_start_and_complete_broadcast():
    """scan_started and scan_complete messages must always be broadcast."""
    manager = _make_connection_manager()
    scanner = _make_scanner([])  # No progress updates

    with patch("auralis.library.scanner.LibraryScanner", return_value=scanner):
        await _background_auto_scan(
            music_source_dir=Path("/fake/music"),
            library_manager=MagicMock(),
            fingerprint_queue=None,
            connection_manager=manager,
        )

    all_types = [c.args[0]["type"] for c in manager.broadcast.call_args_list]
    assert "library_scan_started" in all_types, "scan_started must be broadcast"
    assert "scan_complete" in all_types, "scan_complete must be broadcast"
