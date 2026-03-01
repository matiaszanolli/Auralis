"""
Library Auto-Scanner Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Background service that watches configured music folders and keeps the
library in sync:

- On startup: runs a full scan of all configured folders if auto_scan=True
- Continuous: watches folders with watchdog (real-time) + periodic polling fallback
- Cleanup: removes tracks whose files no longer exist after each scan cycle
- Crash-safe: outer try/except loop restarts after errors with 30s back-off
- Graceful shutdown: asyncio.Event-based stop signaling

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import json
from typing import Any

logger = logging.getLogger(__name__)

# Optional watchdog for real-time filesystem events
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    Observer = None  # type: ignore[assignment,misc]
    FileSystemEventHandler = object  # type: ignore[assignment,misc]


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
        self._schedule()

    def on_deleted(self, event: Any) -> None:
        self._schedule()

    def on_moved(self, event: Any) -> None:
        self._schedule()

    def _schedule(self) -> None:
        # Cancel pending timer and reset; fires 500ms after last event
        if self._pending is not None:
            self._pending.cancel()
        self._pending = self._loop.call_later(
            0.5,
            lambda: self._loop.create_task(self._trigger_fn())
        )


class LibraryAutoScanner:
    """
    Background library auto-scanner with watchdog + polling fallback.

    Usage::

        scanner = LibraryAutoScanner(settings_repo, library_manager,
                                     fingerprint_queue, connection_manager)
        await scanner.start()   # called from lifespan startup
        ...
        await scanner.stop()    # called from lifespan shutdown
        # Call after any settings change that affects scan config:
        await scanner.reload_config()
    """

    def __init__(
        self,
        settings_repo: Any,
        library_manager: Any,
        fingerprint_queue: Any | None,
        connection_manager: Any,
    ) -> None:
        self._settings_repo = settings_repo
        self._library_manager = library_manager
        self._fingerprint_queue = fingerprint_queue
        self._connection_manager = connection_manager

        self._stop_event = asyncio.Event()
        self._trigger_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._observer: Any = None  # watchdog Observer, if available

    # ------------------------------------------------------------------
    # Public lifecycle API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the scanner background task."""
        self._task = asyncio.create_task(self._run(), name="library_auto_scanner")
        if HAS_WATCHDOG:
            logger.info("✅ LibraryAutoScanner started (watchdog + polling fallback)")
        else:
            logger.info("✅ LibraryAutoScanner started (polling-only; install watchdog for real-time detection)")

    async def stop(self) -> None:
        """Signal the scanner to stop and wait for it to finish."""
        self._stop_event.set()
        self._trigger_event.set()  # wake up any sleeping wait
        self._stop_watchdog()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        logger.info("✅ LibraryAutoScanner stopped")

    async def reload_config(self) -> None:
        """
        Wake up the scanner immediately to pick up settings changes.

        Called by the settings router after scan folders or auto_scan change.
        """
        self._trigger_event.set()

    # ------------------------------------------------------------------
    # Internal run loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Outer crash-safe loop."""
        while not self._stop_event.is_set():
            try:
                await self._run_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(f"LibraryAutoScanner cycle failed: {exc}", exc_info=True)
                await connection_manager_safe_broadcast(
                    self._connection_manager,
                    {"type": "library_scan_error", "error": str(exc)}
                )
                # Back off 30s before retry to avoid tight crash-loop
                await self._interruptible_sleep(30)

    async def _run_cycle(self) -> None:
        """One complete scan cycle: read settings, scan, cleanup, sleep."""
        settings = await asyncio.to_thread(self._settings_repo.get_settings)

        scan_folders = _parse_scan_folders(settings)
        auto_scan: bool = bool(settings.auto_scan) if settings else False
        scan_interval: int = int(settings.scan_interval) if settings and settings.scan_interval else 3600

        # Restart watchdog if folder list changed
        self._sync_watchdog(scan_folders)

        if not auto_scan or not scan_folders:
            logger.debug("Auto-scan disabled or no folders configured — waiting for trigger")
            await self._interruptible_sleep(scan_interval)
            return

        await self._do_scan(scan_folders)
        await self._interruptible_sleep(scan_interval)

    async def _do_scan(self, scan_folders: list[str]) -> None:
        """Run a full scan + cleanup cycle."""
        from auralis.library.scanner import LibraryScanner

        logger.info(f"🔍 Auto-scan starting: {scan_folders}")
        await connection_manager_safe_broadcast(
            self._connection_manager,
            {"type": "library_scan_started", "directories": scan_folders}
        )

        scanner = LibraryScanner(
            self._library_manager,
            fingerprint_queue=self._fingerprint_queue
        )

        # Bridge sync scanner progress → async broadcast
        loop = asyncio.get_running_loop()

        async def _async_progress(data: dict[str, Any]) -> None:
            total = data.get('total_found', 0) or data.get('processed', 0)
            processed = data.get('processed', 0)
            frac = data.get('progress', 0)
            pct = round(frac * 100) if frac else (round(processed / total * 100) if total > 0 else 0)
            await connection_manager_safe_broadcast(
                self._connection_manager,
                {
                    "type": "scan_progress",
                    "data": {
                        "current": processed,
                        "total": total,
                        "percentage": pct,
                        "current_file": data.get('current_file') or data.get('file') or data.get('directory'),
                    }
                }
            )

        def sync_progress(data: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(loop.create_task, _async_progress(data))

        scanner.set_progress_callback(sync_progress)

        try:
            scan_result = await asyncio.to_thread(
                scanner.scan_directories,
                scan_folders,
                recursive=True,
                skip_existing=True,
                check_modifications=True,
            )
        except Exception as exc:
            logger.error(f"scan_directories failed: {exc}", exc_info=True)
            await connection_manager_safe_broadcast(
                self._connection_manager,
                {"type": "library_scan_error", "error": str(exc)}
            )
            return

        files_added = scan_result.files_added if scan_result else 0
        logger.info(f"✅ Auto-scan complete: {files_added} files added")

        # Enqueue new tracks for fingerprinting (same pattern as library.py:520-529)
        if scan_result and scan_result.added_tracks and self._fingerprint_queue:
            try:
                from analysis.fingerprint_queue import get_fingerprint_queue
                fp_queue = get_fingerprint_queue()
                if fp_queue:
                    enqueued = sum(1 for t in scan_result.added_tracks if fp_queue.enqueue(t.id))
                    if enqueued:
                        logger.info(f"Enqueued {enqueued} tracks for fingerprinting")
            except Exception as fp_err:
                logger.warning(f"Fingerprint enqueue failed after auto-scan: {fp_err}")

        # Remove tracks whose files no longer exist on disk
        try:
            removed = await asyncio.to_thread(
                self._library_manager.tracks.cleanup_missing_files
            )
            if removed:
                logger.info(f"🗑️  Removed {removed} missing tracks from library")
                await connection_manager_safe_broadcast(
                    self._connection_manager,
                    {"type": "library_tracks_removed", "count": removed}
                )
        except Exception as exc:
            logger.warning(f"cleanup_missing_files failed: {exc}")

        await connection_manager_safe_broadcast(
            self._connection_manager,
            {
                "type": "scan_complete",
                "data": {
                    "files_processed": scan_result.files_processed if scan_result else 0,
                    "files_added": scan_result.files_added if scan_result else 0,
                    "duration": scan_result.scan_time if scan_result else 0,
                }
            }
        )

    async def _interruptible_sleep(self, seconds: int) -> None:
        """
        Sleep for `seconds`, but wake up early if:
        - `_trigger_event` is set (config change or watchdog event)
        - `_stop_event` is set (shutdown)
        """
        self._trigger_event.clear()
        try:
            await asyncio.wait_for(self._trigger_event.wait(), timeout=float(seconds))
        except asyncio.TimeoutError:
            pass  # Normal: slept the full interval

    # ------------------------------------------------------------------
    # Watchdog management
    # ------------------------------------------------------------------

    def _sync_watchdog(self, scan_folders: list[str]) -> None:
        """Start or restart the watchdog observer for the given folders."""
        if not HAS_WATCHDOG:
            return

        # Compare current watched dirs against new list
        current_dirs: set[str] = set()
        if self._observer and self._observer.is_alive():
            current_dirs = {str(w.path) for w in self._observer._watches}  # type: ignore[union-attr]

        new_dirs = set(scan_folders)
        if current_dirs == new_dirs:
            return  # No change

        self._stop_watchdog()
        if not scan_folders:
            return

        try:
            loop = asyncio.get_running_loop()
            handler = _DebounceHandler(trigger_fn=self.reload_config, loop=loop)
            self._observer = Observer()
            for folder in scan_folders:
                self._observer.schedule(handler, folder, recursive=True)
            self._observer.start()
            logger.info(f"👁️  Watchdog watching: {scan_folders}")
        except Exception as exc:
            logger.warning(f"Watchdog setup failed, using polling-only: {exc}")
            self._observer = None

    def _stop_watchdog(self) -> None:
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
            self._observer = None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_scan_folders(settings: Any) -> list[str]:
    """Extract and parse scan_folders from UserSettings object."""
    if not settings or not settings.scan_folders:
        return []
    raw = settings.scan_folders
    if isinstance(raw, str):
        try:
            folders = json.loads(raw)
        except (ValueError, TypeError):
            return []
    elif isinstance(raw, list):
        folders = raw
    else:
        return []
    return [str(f) for f in folders if f]


async def connection_manager_safe_broadcast(manager: Any, message: dict[str, Any]) -> None:
    """Broadcast a message, suppressing errors if no clients are connected."""
    try:
        await manager.broadcast(message)
    except Exception as exc:
        logger.debug(f"Broadcast skipped: {exc}")
