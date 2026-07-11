"""
LibraryAutoScanner Lifecycle Tests (#3923)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`LibraryAutoScanner` (433 LOC) runs a long-lived background asyncio task with
a watchdog + polling fallback, but had no dedicated tests for its lifecycle:
start() creating the task, stop() cancelling it, reload_config() waking a
sleeping cycle, the watchdog debounce handler coalescing filesystem events,
and the polling fallback picking up the configured scan interval.

`tests/backend/test_library_auto_scanner_error_sanitisation.py` covers the
_run() outer crash-loop error-sanitisation behaviour (#3846) only; this file
covers the surrounding lifecycle/config-reload/watchdog/polling surface.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.library_auto_scanner import LibraryAutoScanner, _DebounceHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(auto_scan: bool = False, scan_folders: list[str] | None = None, scan_interval: int = 3600) -> SimpleNamespace:
    return SimpleNamespace(
        auto_scan=auto_scan,
        scan_folders=json.dumps(scan_folders or []),
        scan_interval=scan_interval,
    )


def _make_scanner(settings: SimpleNamespace | None = None) -> tuple[LibraryAutoScanner, MagicMock, MagicMock, MagicMock]:
    settings_repo = MagicMock()
    settings_repo.get_settings = MagicMock(return_value=settings or _make_settings())
    library_manager = MagicMock()
    connection_manager = MagicMock()
    scanner = LibraryAutoScanner(
        settings_repo=settings_repo,
        library_manager=library_manager,
        fingerprint_queue=None,
        connection_manager=connection_manager,
    )
    return scanner, settings_repo, library_manager, connection_manager


# ---------------------------------------------------------------------------
# start() / stop() lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_background_task(self):
        """start() spawns a running background task tracked on the instance."""
        scanner, *_ = _make_scanner()
        try:
            await scanner.start()
            assert scanner._task is not None
            assert isinstance(scanner._task, asyncio.Task)
            assert not scanner._task.done()
        finally:
            await scanner.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task_and_sets_stop_event(self):
        """stop() signals the stop event and the task actually terminates."""
        scanner, *_ = _make_scanner()
        await scanner.start()
        task = scanner._task

        await scanner.stop()

        assert scanner._stop_event.is_set()
        assert task.done()

    @pytest.mark.asyncio
    async def test_stop_is_safe_when_never_started(self):
        """stop() must not raise if start() was never called."""
        scanner, *_ = _make_scanner()
        await scanner.stop()  # should not raise
        assert scanner._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        """Calling stop() twice must not raise or hang."""
        scanner, *_ = _make_scanner()
        await scanner.start()
        await scanner.stop()
        await scanner.stop()  # should not raise
        assert scanner._task.done()


# ---------------------------------------------------------------------------
# reload_config()
# ---------------------------------------------------------------------------

class TestReloadConfig:
    @pytest.mark.asyncio
    async def test_reload_config_is_idempotent(self):
        """Calling reload_config() repeatedly before anything consumes it is safe."""
        scanner, *_ = _make_scanner()
        await scanner.reload_config()
        await scanner.reload_config()
        await scanner.reload_config()
        assert scanner._trigger_event.is_set()

    @pytest.mark.asyncio
    async def test_reload_config_wakes_an_in_progress_sleep_immediately(self):
        """reload_config() must wake _interruptible_sleep() well before the
        configured interval elapses — this is how a settings-change (or a
        watchdog event, via _DebounceHandler) makes the scanner re-check
        its config without waiting out a long poll interval.
        """
        scanner, *_ = _make_scanner()
        sleep_task = asyncio.create_task(scanner._interruptible_sleep(30))
        # Let the sleep actually start waiting on the event before waking it.
        await asyncio.sleep(0)

        start = time.monotonic()
        await scanner.reload_config()
        await asyncio.wait_for(sleep_task, timeout=1.0)
        elapsed = time.monotonic() - start

        assert elapsed < 1.0, f"reload_config() took {elapsed:.2f}s to wake a sleeping cycle"

    @pytest.mark.asyncio
    async def test_interruptible_sleep_wakes_on_stop_event(self):
        """stop() (which also sets _trigger_event) wakes a sleeping cycle, not
        just a full reload_config()."""
        scanner, *_ = _make_scanner()
        sleep_task = asyncio.create_task(scanner._interruptible_sleep(30))
        await asyncio.sleep(0)

        start = time.monotonic()
        scanner._stop_event.set()
        scanner._trigger_event.set()
        await asyncio.wait_for(sleep_task, timeout=1.0)
        elapsed = time.monotonic() - start

        assert elapsed < 1.0


# ---------------------------------------------------------------------------
# Polling fallback / _run_cycle
# ---------------------------------------------------------------------------

class TestRunCyclePolling:
    @pytest.mark.asyncio
    async def test_run_cycle_scans_and_sleeps_configured_interval_when_enabled(self):
        """With auto_scan=True and folders configured, one cycle scans once
        and then sleeps for exactly the configured interval."""
        settings = _make_settings(auto_scan=True, scan_folders=["/music"], scan_interval=1234)
        scanner, *_ = _make_scanner(settings)

        scanner._do_scan = AsyncMock()  # type: ignore[method-assign]
        sleep_calls: list[int] = []

        async def _record_sleep(seconds: int) -> None:
            sleep_calls.append(seconds)

        scanner._interruptible_sleep = _record_sleep  # type: ignore[method-assign]

        await scanner._run_cycle()

        scanner._do_scan.assert_awaited_once_with(["/music"])
        assert sleep_calls == [1234]

    @pytest.mark.asyncio
    async def test_run_cycle_skips_scan_when_auto_scan_disabled(self):
        """With auto_scan=False, _do_scan is never invoked — only the
        interruptible sleep runs (polling for a future config change)."""
        settings = _make_settings(auto_scan=False, scan_folders=["/music"], scan_interval=60)
        scanner, *_ = _make_scanner(settings)

        scanner._do_scan = AsyncMock()  # type: ignore[method-assign]
        sleep_calls: list[int] = []

        async def _record_sleep(seconds: int) -> None:
            sleep_calls.append(seconds)

        scanner._interruptible_sleep = _record_sleep  # type: ignore[method-assign]

        await scanner._run_cycle()

        scanner._do_scan.assert_not_awaited()
        assert sleep_calls == [60]

    @pytest.mark.asyncio
    async def test_run_cycle_skips_scan_when_no_folders_configured(self):
        """auto_scan=True but no folders configured behaves like disabled."""
        settings = _make_settings(auto_scan=True, scan_folders=[], scan_interval=60)
        scanner, *_ = _make_scanner(settings)

        scanner._do_scan = AsyncMock()  # type: ignore[method-assign]
        scanner._interruptible_sleep = AsyncMock()  # type: ignore[method-assign]

        await scanner._run_cycle()

        scanner._do_scan.assert_not_awaited()
        scanner._interruptible_sleep.assert_awaited_once_with(60)


# ---------------------------------------------------------------------------
# Watchdog: debounce handler + _sync_watchdog wiring
# ---------------------------------------------------------------------------

class TestWatchdogDebounce:
    @pytest.mark.asyncio
    async def test_rapid_events_coalesce_into_a_single_trigger(self):
        """_DebounceHandler must coalesce a burst of filesystem events into
        exactly one trigger_fn call 500ms after the last event — not one
        call per event."""
        loop = asyncio.get_running_loop()
        trigger_calls = 0

        async def _trigger() -> None:
            nonlocal trigger_calls
            trigger_calls += 1

        handler = _DebounceHandler(trigger_fn=_trigger, loop=loop)

        # Simulate a burst of rapid events (e.g. moving an album folder).
        for _ in range(5):
            handler.on_created(None)
            handler.on_deleted(None)
            handler.on_moved(None)
            await asyncio.sleep(0.01)

        # Nothing should have fired yet — still within the 500ms debounce window.
        assert trigger_calls == 0

        # Wait past the debounce window.
        await asyncio.sleep(0.6)

        assert trigger_calls == 1

    @pytest.mark.asyncio
    async def test_events_after_debounce_window_trigger_again(self):
        """A second burst, after the first has fired, produces a second trigger."""
        loop = asyncio.get_running_loop()
        trigger_calls = 0

        async def _trigger() -> None:
            nonlocal trigger_calls
            trigger_calls += 1

        handler = _DebounceHandler(trigger_fn=_trigger, loop=loop)

        handler.on_created(None)
        await asyncio.sleep(0.6)
        assert trigger_calls == 1

        handler.on_created(None)
        await asyncio.sleep(0.6)
        assert trigger_calls == 2


class TestSyncWatchdog:
    """_sync_watchdog() starts/restarts the watchdog Observer as scan_folders
    change. Patches HAS_WATCHDOG + Observer since the `watchdog` package is
    an optional dependency not guaranteed to be installed in the test env."""

    @pytest.mark.asyncio
    async def test_sync_watchdog_starts_observer_for_new_folders(self):
        scanner, *_ = _make_scanner()

        mock_observer_instance = MagicMock()
        mock_observer_instance._watches = []
        mock_observer_cls = MagicMock(return_value=mock_observer_instance)

        with patch("services.library_auto_scanner.HAS_WATCHDOG", True), \
             patch("services.library_auto_scanner.Observer", mock_observer_cls):
            scanner._sync_watchdog(["/music"])

        mock_observer_cls.assert_called_once()
        mock_observer_instance.schedule.assert_called_once()
        mock_observer_instance.start.assert_called_once()
        assert scanner._observer is mock_observer_instance

    @pytest.mark.asyncio
    async def test_sync_watchdog_noop_when_folders_unchanged(self):
        scanner, *_ = _make_scanner()

        mock_observer_instance = MagicMock()
        mock_observer_instance.is_alive.return_value = True
        watch = MagicMock()
        watch.path = "/music"
        mock_observer_instance._watches = [watch]
        scanner._observer = mock_observer_instance

        with patch("services.library_auto_scanner.HAS_WATCHDOG", True), \
             patch("services.library_auto_scanner.Observer") as mock_observer_cls:
            scanner._sync_watchdog(["/music"])

        mock_observer_cls.assert_not_called()
        mock_observer_instance.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_watchdog_restarts_when_folders_change(self):
        scanner, *_ = _make_scanner()

        old_observer = MagicMock()
        old_observer.is_alive.return_value = True
        old_watch = MagicMock()
        old_watch.path = "/old"
        old_observer._watches = [old_watch]
        scanner._observer = old_observer

        new_observer_instance = MagicMock()
        new_observer_instance._watches = []
        mock_observer_cls = MagicMock(return_value=new_observer_instance)

        with patch("services.library_auto_scanner.HAS_WATCHDOG", True), \
             patch("services.library_auto_scanner.Observer", mock_observer_cls):
            scanner._sync_watchdog(["/new"])

        old_observer.stop.assert_called_once()
        mock_observer_cls.assert_called_once()
        new_observer_instance.schedule.assert_called_once()
        assert scanner._observer is new_observer_instance

    def test_sync_watchdog_is_noop_without_watchdog_installed(self):
        """When HAS_WATCHDOG is False (package not installed), _sync_watchdog
        must not touch self._observer at all."""
        scanner, *_ = _make_scanner()
        with patch("services.library_auto_scanner.HAS_WATCHDOG", False):
            scanner._sync_watchdog(["/music"])
        assert scanner._observer is None
