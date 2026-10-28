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
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import json
import logging

from config.limits import MAX_SCAN_INTERVAL_S, MIN_SCAN_INTERVAL_S, SHUTDOWN_STEP_TIMEOUT_S
from typing import Any

from helpers import spawn_background_task
from websocket.outbound_messages import broadcast_typed

from .missing_tracks import prune_missing_tracks
from .scan_events import make_progress_callback, scan_complete_payload
from .scan_fingerprint_enqueue import enqueue_scanned_for_fingerprinting
from .scanner_stop import stop_scanner
from .scanner_watchdog import HAS_WATCHDOG, WatchdogMixin

logger = logging.getLogger(__name__)


class LibraryAutoScanner(WatchdogMixin):
    """
    Background library auto-scanner with watchdog + polling fallback.

    Usage::

        scanner = LibraryAutoScanner(settings_repo, library_database,
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
        library_database: Any,
        fingerprint_queue: Any | None,
        connection_manager: Any,
        on_scan_complete: Any | None = None,
    ) -> None:
        self._settings_repo = settings_repo
        self._library_database = library_database
        self._fingerprint_queue = fingerprint_queue
        self._connection_manager = connection_manager
        # #3479: optional callback invoked at the end of each scan; receives
        # the ScanResult. Wired by startup.py to refresh the reference cloud.
        self._on_scan_complete = on_scan_complete

        self._stop_event = asyncio.Event()
        self._trigger_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._observer: Any = None  # watchdog Observer, if available

    # ------------------------------------------------------------------
    # Public lifecycle API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the scanner background task."""
        self._task = spawn_background_task(self._run(), name="library_auto_scanner")
        if HAS_WATCHDOG:
            logger.info("✅ LibraryAutoScanner started (watchdog + polling fallback)")
        else:
            logger.info("✅ LibraryAutoScanner started (polling-only; install watchdog for real-time detection)")

    async def stop(self) -> None:
        """Signal the scanner to stop and wait for it to finish."""
        self._stop_event.set()
        self._trigger_event.set()  # wake up any sleeping wait
        # Observer.join() blocks up to OBSERVER_JOIN_TIMEOUT_S; offload so shutdown doesn't stall
        # the event loop for up to 5s (#4775).
        await asyncio.to_thread(self._stop_watchdog)
        if self._task and not self._task.done():
            self._task.cancel()
            # wait(), not wait_for(): it never raises the task's own cancellation (#6092).
            await asyncio.wait({self._task}, timeout=SHUTDOWN_STEP_TIMEOUT_S)
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
                await broadcast_typed(
                    self._connection_manager,
                    "library_scan_error",
                    {
                        # Mirror the inner _do_scan handler (#3543): surface only the
                        # exception class so OS paths / permission detail don't leak
                        # to every connected client (fixes #3846 / BE-EH-3).
                        "error": f"{type(exc).__name__} during library scan",
                    },
                    suppress_errors=True,
                )
                # Back off 30s before retry to avoid tight crash-loop
                await self._interruptible_sleep(30)

    async def _run_cycle(self) -> None:
        """One complete scan cycle: read settings, scan, cleanup, sleep."""
        # Consume the wake-up before anything this cycle reads, not in the sleep:
        # a trigger raised during the settings read or the scan must survive (#5881).
        self._trigger_event.clear()
        settings = await asyncio.to_thread(self._settings_repo.get_settings)

        scan_folders = _parse_scan_folders(settings)
        auto_scan: bool = bool(settings.auto_scan) if settings else False
        scan_interval: int = int(settings.scan_interval) if settings and settings.scan_interval else 3600
        # A stored value from before the request bound existed (#6164) must not
        # turn into a rescan every few seconds.
        scan_interval = min(max(scan_interval, MIN_SCAN_INTERVAL_S), MAX_SCAN_INTERVAL_S)

        # Restart watchdog if folder list changed
        await self._sync_watchdog(scan_folders)

        if not auto_scan or not scan_folders:
            logger.debug("Auto-scan disabled or no folders configured — waiting for trigger")
            await self._interruptible_sleep(scan_interval)
            return

        await self._do_scan(scan_folders)
        await self._interruptible_sleep(scan_interval)

    async def _do_scan(self, scan_folders: list[str]) -> None:
        """Run a full scan + cleanup cycle."""
        from auralis.library.scanner import LibraryScanner

        logger.info(f"🔍 Auto-scan starting ({len(scan_folders)} folder(s))")
        logger.debug(f"Auto-scan folders: {scan_folders}")

        # NOTE: `library_scan_started` is NOT broadcast here (#4602). This
        # emitter had the identical ordering bug as the manual route — it fired
        # before LibraryScanner was even constructed, so an auto-scan that the
        # concurrency guard then rejected still reset the UI counters of a
        # manual scan already in flight. The scanner emits a `stage: 'started'`
        # progress event once it owns the scan slot; make_progress_callback turns
        # that into the frame.

        # No fingerprint_queue: the scanner never enqueued (#4648, #2382).
        # This class does its own enqueueing after the scan returns.
        scanner = LibraryScanner(self._library_database)

        scanner.set_progress_callback(
            make_progress_callback(
                asyncio.get_running_loop(), self._connection_manager, scan_folders
            )
        )

        # #3479: wire the reference-cloud refresh callback if configured.
        if self._on_scan_complete is not None:
            scanner.set_scan_complete_callback(self._on_scan_complete)

        # #3710: keep the to_thread future so a cancellation (lifespan shutdown)
        # can signal should_stop instead of releasing the scan slot while the
        # thread is still running and racing a later manual scan.
        scan_future = asyncio.ensure_future(asyncio.to_thread(
            scanner.scan_directories,
            scan_folders,
            recursive=True,
            skip_existing=True,
            check_modifications=True,
        ))
        try:
            scan_result = await asyncio.shield(scan_future)
        except asyncio.CancelledError:
            # Shared with the manual-scan endpoint (#5196). It also swallows a
            # scan failure raised during the grace wait, which used to escape
            # here and replace this CancelledError.
            await stop_scanner(scanner, scan_future, label="Auto-scanner")
            raise
        except Exception as exc:
            # Full detail server-side, a class-based summary on the wire (#3543).
            logger.error(f"scan_directories failed: {exc}", exc_info=True)
            scan_error: str | None = f"{type(exc).__name__} during library scan"
        else:
            # The scanner's own catch-all reports the same way (#5877).
            scan_error = scan_result.error
        if scan_error:
            await broadcast_typed(
                self._connection_manager, "library_scan_error", {"error": scan_error}, suppress_errors=True,
            )
            return

        if scan_result.rejected:
            # Lost the scan-slot race: the scan holding the slot broadcasts its
            # own scan_complete, and an all-zero one from here would reset the
            # UI's view of it (#5465). Mirrors the manual router's 409.
            logger.debug("Auto-scan cycle rejected (scan slot held elsewhere); skipping this cycle")
            return

        files_added = scan_result.files_added if scan_result else 0
        logger.info(f"✅ Auto-scan complete: {files_added} files added")

        if self._fingerprint_queue and scan_result:  # only when handed a queue
            await enqueue_scanned_for_fingerprinting(scan_result)

        # Remove tracks whose files no longer exist on disk (shared with the
        # manual scan route, #5458) — unless a folder was unreadable: a
        # configured folder on an unplugged drive would lose every track (#5877).
        removed = 0
        if scan_result.walk_complete:
            removed = await prune_missing_tracks(self._library_database, self._connection_manager)

        await broadcast_typed(
            self._connection_manager,
            "scan_complete",
            scan_complete_payload(scan_result),
            suppress_errors=True,
        )

        # Fields here must match LibraryUpdatedMessage in
        # frontend/src/types/ws/library.ts.
        if files_added or removed:
            await broadcast_typed(
                self._connection_manager,
                "library_updated",
                {
                    "action": "scan",
                    "track_count": files_added,
                },
                suppress_errors=True,
            )

    async def _interruptible_sleep(self, seconds: int) -> None:
        """
        Sleep for `seconds`, waking early on `_trigger_event` (config change,
        watchdog event, shutdown). One already set returns at once (#5881).
        """
        if self._stop_event.is_set():
            return
        try:
            await asyncio.wait_for(self._trigger_event.wait(), timeout=float(seconds))
        except TimeoutError:
            pass  # Normal: slept the full interval


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
