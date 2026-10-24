"""
Scan-progress and result publishing for LibraryAutoScanner (split from
library_auto_scanner.py, #5837).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, cast

from helpers import log_task_exception, scan_progress_percentage
from websocket.outbound.library import ScanCompletePayload, ScanFailurePayload
from websocket.outbound_messages import broadcast_typed

logger = logging.getLogger(__name__)


def make_progress_callback(
    loop: asyncio.AbstractEventLoop,
    connection_manager: Any,
    scan_folders: list[str],
) -> Callable[[dict[str, Any]], None]:
    """Bridge the scanner's synchronous progress callback to async WebSocket broadcasts."""

    async def _async_progress(data: dict[str, Any]) -> None:
        # Emitted only once the scanner owns the scan slot, so this is the
        # earliest truthful start frame (#4602).
        if data.get('stage') == 'started':
            # `scan_folders` are the user's configured auto-scan folders
            # (Settings), same disclosure class as the manual route's
            # request.directories — a value the user already knows, not
            # one the server introduced. Deliberately not redacted like
            # the library_scan_error frames, which echo an
            # *unhandled exception's message* and can name paths the user
            # never chose (#4651, same policy as routers/library_scan.py).
            await broadcast_typed(
                connection_manager,
                "library_scan_started",
                {"directories": data.get('directories') or scan_folders},
                suppress_errors=True,
            )
            return
        # Prefer the pre-counted total (#4616), same as the manual emitter.
        total = (
            data.get('total_expected')
            or data.get('total_found', 0)
            or data.get('processed', 0)
        )
        processed = data.get('processed', 0)
        # Shared with the manual scan emitter: indeterminate unless a real
        # `progress` fraction is supplied (#4411 / F4-04).
        pct = scan_progress_percentage(data)
        await broadcast_typed(
            connection_manager,
            "scan_progress",
            {
                "current": processed,
                "total": total,
                "percentage": pct,
                # Same policy as library_scan_started above (#4651):
                # this path lives under a user-chosen folder, and the
                # frontend's ScanStatusCard surfaces it verbatim in a
                # tooltip by design.
                "current_file": data.get('current_file') or data.get('file') or data.get('directory'),
                "phase": data.get('stage', 'processing'),
            },
            suppress_errors=True,
        )

    def sync_progress(data: dict[str, Any]) -> None:
        # Schedule the async broadcaster on the event loop with a
        # done-callback so failures are logged instead of silently
        # dropped (fixes #3512 / BE-NEW-54).
        def _schedule() -> None:
            task = loop.create_task(_async_progress(data))
            task.add_done_callback(log_task_exception)
        loop.call_soon_threadsafe(_schedule)

    return sync_progress


async def enqueue_added_for_fingerprinting(fingerprint_queue: Any, scan_result: Any) -> None:
    """Enqueue newly added tracks for fingerprinting (same pattern as the manual route)."""
    if not (scan_result and scan_result.added_tracks and fingerprint_queue):
        return
    try:
        from analysis.fingerprint_queue import get_fingerprint_queue
        fp_queue = get_fingerprint_queue()
        if fp_queue:
            enqueued = await asyncio.to_thread(
                lambda: sum(
                    1 for t in scan_result.added_tracks if fp_queue.enqueue(t.id)
                )
            )
            if enqueued:
                logger.info(f"Enqueued {enqueued} tracks for fingerprinting")
    except Exception as fp_err:
        logger.warning(f"Fingerprint enqueue failed after auto-scan: {fp_err}")


def scan_complete_payload(scan_result: Any) -> ScanCompletePayload:
    """Canonical scan_complete payload (matches the manual-scan emit and the
    frontend ScanCompleteMessage type).

    Fixes #3502 — extras (files_updated / files_skipped / directories_scanned)
    are included for parity with the manual path.
    """
    return {
        "files_processed": scan_result.files_processed if scan_result else 0,
        "files_added": scan_result.files_added if scan_result else 0,
        "files_updated": scan_result.files_updated if scan_result else 0,
        "files_skipped": scan_result.files_skipped if scan_result else 0,
        "files_failed": scan_result.files_failed if scan_result else 0,
        # #4841: kept identical to the manual-scan emit.
        "failures": [
            cast(ScanFailurePayload, failure.to_dict())
            for failure in scan_result.failures
        ]
        if scan_result
        else [],
        "duration": scan_result.scan_time if scan_result else 0,
        "directories_scanned": scan_result.directories_scanned if scan_result else 0,
    }
