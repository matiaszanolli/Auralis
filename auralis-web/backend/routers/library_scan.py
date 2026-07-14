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

from schemas import LibraryScanRequest, ScanResultResponse
from helpers import scan_progress_percentage

from .errors import handle_query_error

logger = logging.getLogger(__name__)


def create_library_scan_router(
    get_library_manager: Callable[[], Any] | None = None,
    connection_manager: Any | None = None,
) -> APIRouter:
    """Factory: library scan route."""
    router = APIRouter(tags=["library"])

    @router.post("/api/library/scan", response_model=ScanResultResponse)
    async def scan_library(request: LibraryScanRequest) -> ScanResultResponse:
        """Scan directories for audio files and add them to the library.

        Progress updates are broadcast via WebSocket (see WEBSOCKET_API.md).
        """
        try:
            from auralis.library.scanner import LibraryScanner

            if not get_library_manager:
                raise HTTPException(status_code=503, detail="Library manager not available")

            library_manager = get_library_manager()
            scanner = LibraryScanner(library_manager)

            # Broadcast scan started so frontend shows status immediately (#2711)
            if connection_manager:
                await connection_manager.broadcast({
                    "type": "library_scan_started",
                    "data": {"directories": request.directories},
                })

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
                        total = progress_data.get('total_found', 0) or progress_data.get('processed', 0)
                        processed = progress_data.get('processed', 0)
                        # Indeterminate unless the scanner supplies a real fraction
                        # (streaming scan makes processed/total meaningless) — #4411.
                        percentage = scan_progress_percentage(progress_data)
                        stage = progress_data.get('stage', 'processing')
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
                        enqueued = sum(1 for t in result.added_tracks if fp_queue.enqueue(t.id))
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
                duration=result.scan_time,
                directories_scanned=result.directories_scanned,
            )

        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail=f"Library scan timed out after {scan_timeout}s")
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("scan library", e)

    return router
