"""
Watchdog glue for LibraryAutoScanner (split from library_auto_scanner.py, #5837):
the optional import, the debounced event handler, and the observer start/stop.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any
from collections.abc import Callable, Coroutine

from config.limits import OBSERVER_JOIN_TIMEOUT_S

from .scanner_event_filter import is_relevant_event

logger = logging.getLogger(__name__)

# Optional watchdog for real-time filesystem events
try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    Observer = None
    FileSystemEventHandler = object


class _DebounceHandler(FileSystemEventHandler):  # type: ignore[misc]
    """
    Watchdog event handler with 500ms debounce.

    Coalesces rapid filesystem events (e.g. moving an album folder) into a
    single scan trigger, avoiding cascading scans on large file operations.
    """

    def __init__(self, trigger_fn: Any, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._trigger_fn = trigger_fn
        self._loop = loop
        self._pending: asyncio.TimerHandle | None = None

    def on_created(self, event: Any) -> None:
        self._schedule_if_relevant(event)

    def on_deleted(self, event: Any) -> None:
        self._schedule_if_relevant(event)

    def on_moved(self, event: Any) -> None:
        self._schedule_if_relevant(event)

    def _schedule_if_relevant(self, event: Any) -> None:
        if is_relevant_event(event):  # audio, cover art or a directory; not .part/swap/app temp (#6164)
            self._schedule()

    def _schedule(self) -> None:
        # Runs on the watchdog thread: call_later and TimerHandle.cancel are not thread-safe from
        # here (#2863), so the cancel-and-reschedule is deferred to the loop thread (#4748).
        self._loop.call_soon_threadsafe(self._schedule_on_loop)

    def _schedule_on_loop(self) -> None:
        """Schedule the debounced callback from within the event loop thread."""
        if self._pending is not None:
            self._pending.cancel()
        self._pending = self._loop.call_later(
            0.5,
            lambda: self._loop.create_task(self._trigger_fn())
        )


class WatchdogMixin:
    """Observer lifecycle; ``_observer`` and ``reload_config`` belong to LibraryAutoScanner."""

    _observer: Any
    _stop_event: asyncio.Event  # Provided by LibraryAutoScanner.
    # Provided by LibraryAutoScanner (async).
    reload_config: "Callable[[], Coroutine[Any, Any, None]]"

    async def _sync_watchdog(self, scan_folders: list[str]) -> None:
        """Start or restart the watchdog observer for the given folders."""
        if not HAS_WATCHDOG:
            return

        current_dirs: set[str] = set()
        if self._observer and self._observer.is_alive():
            current_dirs = {str(w.path) for w in self._observer._watches}

        new_dirs = set(scan_folders)
        if current_dirs == new_dirs:
            return  # No change

        # join() blocks up to OBSERVER_JOIN_TIMEOUT_S, so offload it (#4775). stop() can land
        # during that await; it sets _stop_event first, so re-check or the Observer leaks (#6098).
        await asyncio.to_thread(self._stop_watchdog)
        if not scan_folders or self._stop_event.is_set():
            return

        try:
            loop = asyncio.get_running_loop()
            handler = _DebounceHandler(trigger_fn=self.reload_config, loop=loop)
            self._observer = Observer()
            for folder in scan_folders:
                self._observer.schedule(handler, folder, recursive=True)
            self._observer.start()
            logger.info(f"👁️  Watchdog watching {len(scan_folders)} folder(s)")
            logger.debug(f"Watchdog folders: {scan_folders}")
        except Exception as exc:
            logger.warning(f"Watchdog setup failed, using polling-only: {exc}")
            self._observer = None

    def _stop_watchdog(self) -> None:
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=OBSERVER_JOIN_TIMEOUT_S)
            except Exception:
                # Best-effort teardown; logged, not swallowed (#4368).
                logger.debug("Watchdog teardown failed", exc_info=True)
            self._observer = None
