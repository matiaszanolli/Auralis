"""
Library Scan Router
~~~~~~~~~~~~~~~~~~~~

Scan-domain endpoint: directory scan with async progress broadcast.

Endpoints:
- POST /api/library/scan - Scan directories and import audio files

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import os
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from schemas import LibraryScanRequest, ScanResultResponse
from helpers import scan_progress_percentage

from .errors import handle_query_error

logger = logging.getLogger(__name__)


class ScanStatusResponse(BaseModel):
    """Live scan-slot state, for a client resyncing mid-scan (#4821)."""
    is_scanning: bool = Field(description="True while a directory scan holds the scan slot")


def create_library_scan_router(
    get_library_manager: Callable[[], Any] | None = None,
    connection_manager: Any | None = None,
) -> APIRouter:
    """Factory: library scan route."""
    router = APIRouter(tags=["library"])

    @router.get("/api/library/scan/status", response_model=ScanStatusResponse)
    async def get_scan_status() -> dict[str, Any]:
        """Resync point for a client that (re)connects mid-scan or after one
        finished while its WebSocket was disconnected (#4821).

        Scan lifecycle (`library_scan_started`/`scan_progress`/`scan_complete`/
        `library_scan_error`) is otherwise broadcast-only — a client offline
        when the terminal frame goes out never learns the scan ended, and
        `isScanning` gets stuck. This is a live read of the same scan-slot
        counter try_acquire_scan_slot()/release_scan_slot() maintain, so it
        self-heals even after a scan crashed without emitting a terminal frame.
        """
        library_manager = get_library_manager() if get_library_manager else None
        if library_manager is None:
            raise HTTPException(status_code=503, detail="Library manager not available")
        return {"is_scanning": library_manager.is_scanning()}

    @router.post("/api/library/scan", response_model=ScanResultResponse)
    async def scan_library(request: LibraryScanRequest) -> ScanResultResponse:
        """Scan directories for audio files and add them to the library.

        Progress updates are broadcast via WebSocket (see WEBSOCKET_API.md).
        """
        try:
            from auralis.library.scanner import LibraryScanner

            # Guard the *resolved* manager, not the getter: the getter is always
            # truthy, so the previous check never fired and a None manager
            # reached LibraryScanner as an opaque 500 (#4656).
            library_manager = get_library_manager() if get_library_manager else None
            if library_manager is None:
                raise HTTPException(status_code=503, detail="Library manager not available")

            scanner = LibraryScanner(library_manager)

            # NOTE: `library_scan_started` is NOT broadcast here (#4602). It used
            # to be sent unconditionally on entry — before scan_directories() ran
            # and long before `result.rejected` could be known — so a second scan
            # request that ended up 409'd had already told the UI a scan began,
            # and its handler resets every counter, destroying the live progress
            # of the scan actually running. The scanner now emits a
            # `stage: 'started'` progress event once it owns the scan slot, and
            # the callback below translates that into the frame (#2711's intent,
            # correctly ordered).

            # Set up progress callback that bridges sync scanner → async broadcast.
            # asyncio.to_thread runs the scanner in a worker thread, so we use
            # loop.call_soon_threadsafe to schedule the async broadcast safely.
            if connection_manager:
                loop = asyncio.get_running_loop()

                def _progress_callback(progress_data: dict[str, Any]) -> None:
                    # Guard against malformed progress_data (e.g. non-dict emitted
                    # by a scanner bug) so a future exception is logged rather than
                    # silently swallowed by run_coroutine_threadsafe (fixes #3864).
                    try:
                        stage = progress_data.get('stage', 'processing')
                        # The scanner emits this only once both rejection guards
                        # have passed, so it is the earliest point at which a
                        # start frame is truthful (#4602).
                        if stage == 'started':
                            asyncio.run_coroutine_threadsafe(
                                connection_manager.broadcast({
                                    "type": "library_scan_started",
                                    "data": {
                                        "directories": progress_data.get('directories')
                                        or request.directories,
                                    },
                                }),
                                loop,
                            )
                            return
                        # Prefer the pre-counted total (#4616) — `total_found`
                        # is the running discovery tally, which tracks
                        # `processed` in lockstep under the streaming scan.
                        total = (
                            progress_data.get('total_expected')
                            or progress_data.get('total_found', 0)
                            or progress_data.get('processed', 0)
                        )
                        processed = progress_data.get('processed', 0)
                        # Indeterminate unless the scanner supplies a real fraction
                        # (streaming scan makes processed/total meaningless) — #4411.
                        percentage = scan_progress_percentage(progress_data)
                        asyncio.run_coroutine_threadsafe(
                            connection_manager.broadcast({
                                "type": "scan_progress",
                                "data": {
                                    "current": processed,
                                    "total": total,
                                    "percentage": percentage,
                                    "current_file": progress_data.get('current_file') or progress_data.get('file'),
                                    "phase": stage,
                                },
                            }),
                            loop,
                        )
                    except Exception:
                        logger.warning(
                            "scan_library progress callback failed — malformed progress_data",
                            exc_info=True,
                        )

                scanner.set_progress_callback(_progress_callback)

            scan_timeout = float(os.environ.get("AURALIS_SCAN_TIMEOUT", "3600"))
            # #3710: capture the to_thread future so we can signal the scanner
            # to stop on cancellation/timeout — asyncio.wait_for cancels the
            # awaitable but cannot terminate the underlying thread without this.
            scan_future = asyncio.ensure_future(asyncio.to_thread(
                scanner.scan_directories,
                directories=request.directories,
                recursive=request.recursive,
                skip_existing=request.skip_existing,
                check_modifications=True,
            ))
            try:
                result = await asyncio.wait_for(asyncio.shield(scan_future), timeout=scan_timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                scanner.stop_scan()
                try:
                    await asyncio.wait_for(asyncio.shield(scan_future), timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    logger.warning(
                        "Scanner thread did not exit within 5s of stop_scan(); "
                        "thread will continue in background until next checkpoint."
                    )
                raise

            # Rejected scan (e.g., already in progress) — return 409 (#2870).
            if result.rejected:
                raise HTTPException(status_code=409, detail="Scan already in progress")

            # Enqueue newly added tracks for background fingerprinting (#2382).
            if result.added_tracks:
                try:
                    from analysis.fingerprint_queue import get_fingerprint_queue
                    fp_queue = get_fingerprint_queue()
                    if fp_queue:
                        # Offloaded (#4702): this is a comprehension over every
                        # newly-added track, so unlike the single-track call
                        # sites its cost scales with scan size — a large import
                        # would hold the loop for the whole sweep, stalling
                        # audio streaming and the scan_complete broadcast below.
                        # The whole loop is offloaded rather than each enqueue,
                        # matching the batch pattern in fingerprint_queue.py
                        # (#3335): one hop instead of N.
                        def _enqueue_added() -> int:
                            return sum(1 for t in result.added_tracks if fp_queue.enqueue(t.id))

                        enqueued = await asyncio.to_thread(_enqueue_added)
                        if enqueued:
                            logger.info(f"Enqueued {enqueued} tracks for fingerprinting after scan")
                except Exception as fp_err:
                    logger.warning(f"Fingerprint enqueue failed after scan: {fp_err}")

            # Broadcast final result. Field shape matches ScanCompleteMessage and
            # the auto-scanner path (services/library_auto_scanner.py:268-279,
            # fixes #3502 — prior `scan_time` was unread by the frontend).
            if connection_manager:
                await connection_manager.broadcast({
                    "type": "scan_complete",
                    "data": {
                        "files_processed": result.files_processed or result.files_found,
                        "files_added": result.files_added,
                        "files_updated": result.files_updated,
                        "files_skipped": result.files_skipped,
                        "files_failed": result.files_failed,
                        # #4841: name the failed files, not just the count.
                        "failures": [f.to_dict() for f in result.failures],
                        "duration": result.scan_time,
                        "directories_scanned": result.directories_scanned,
                    },
                })
                if result.files_added or result.files_updated:
                    await connection_manager.broadcast({
                        "type": "library_updated",
                        # `reason` kept for backward compat; new consumers use `action` (#3544).
                        "data": {
                            "action": "scan",
                            "reason": "scan",
                            "track_count": result.files_added,
                        },
                    })

            return ScanResultResponse(
                files_found=result.files_found,
                files_added=result.files_added,
                files_updated=result.files_updated,
                files_skipped=result.files_skipped,
                files_failed=result.files_failed,
                failures=[f.to_dict() for f in result.failures],
                duration=result.scan_time,
                directories_scanned=result.directories_scanned,
            )

        except asyncio.TimeoutError:
            # Terminal WS frame so a `library_scan_started`-driven UI leaves the
            # scanning state instead of hanging on "Scanning..." (#4413). Mirrors
            # the auto-scanner's error broadcast; no OS paths leak (#3543).
            if connection_manager:
                await connection_manager.broadcast({
                    "type": "library_scan_error",
                    "data": {"error": f"library scan timed out after {int(scan_timeout)}s"},
                })
            raise HTTPException(status_code=504, detail=f"Library scan timed out after {scan_timeout}s")
        except asyncio.CancelledError:
            # The one exit #4413 missed. Since Python 3.8 CancelledError derives
            # from BaseException, so `except Exception` below never caught it and
            # there was no `finally` — the handler simply left, with no terminal
            # frame. `useScanProgress` clears `isScanning` only on scan_complete
            # or library_scan_error, so the panel stayed on "Scanning…" for the
            # rest of the session with tracks half-imported, recoverable only by
            # a page reload. The frontend has two triggers that cancel this
            # request (unmount and supersede), plus server shutdown.
            #
            # Must be ordered before `except Exception` (which cannot catch it
            # anyway) and kept separate from the `except (TimeoutError,
            # CancelledError)` at the wait_for above, which re-raises
            # deliberately after stop_scan(). TimeoutError still reaches its own
            # handler above: it is an Exception subclass, not this one.
            if connection_manager:
                await connection_manager.broadcast({
                    "type": "library_scan_error",
                    "data": {"error": "library scan cancelled"},
                })
            # Re-raise: swallowing CancelledError breaks structured cancellation
            # and uvicorn's shutdown semantics.
            raise
        except HTTPException:
            # Includes the 409 "already in progress" path: another scan owns the
            # UI state and will emit its own terminal frame, so we must NOT clear
            # it here.
            raise
        except Exception as e:
            # Class-name-only redaction, matching the auto-scanner (#3543), so a
            # 500 also releases the scanning state (#4413).
            if connection_manager:
                await connection_manager.broadcast({
                    "type": "library_scan_error",
                    "data": {"error": f"{type(e).__name__} during library scan"},
                })
            raise handle_query_error("scan library", e)

    return router
