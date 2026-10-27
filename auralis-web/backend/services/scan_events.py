"""
Scan-progress and result publishing shared by the manual scan route
(routers/library_scan.py) and LibraryAutoScanner (services/library_auto_scanner.py).

The two paths used to carry near-identical copies of this logic and drifted:
the directory fallback for ``current_file``, exception logging on the progress
bridge and the ``files_processed`` fallback each existed on only one side
(#5912). Everything that must be identical on the wire lives here.

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

from .scan_fingerprint_enqueue import enqueue_scanned_for_fingerprinting  # noqa: F401 — re-exported: the two scan sites import everything scan-related from here

logger = logging.getLogger(__name__)


def make_progress_callback(
    loop: asyncio.AbstractEventLoop,
    connection_manager: Any,
    fallback_dirs: list[str],
) -> Callable[[dict[str, Any]], None]:
    """Bridge the scanner's synchronous progress callback to async WebSocket broadcasts.

    ``fallback_dirs`` are the directories the user chose for this scan (the
    request's directories, or the configured auto-scan folders); they name the
    ``library_scan_started`` frame when the scanner's own event carries none.
    """

    async def _async_progress(data: dict[str, Any]) -> None:
        # Emitted only once the scanner owns the scan slot, so this is the
        # earliest truthful start frame (#4602).
        if data.get('stage') == 'started':
            # `fallback_dirs` is a value the user already knows (a directory
            # dialog pick, or their configured auto-scan folders), not a path
            # the server introduced. Deliberately not redacted like the
            # library_scan_error frames, which echo an *unhandled exception's
            # message* and can name paths the user never chose (#4651).
            await broadcast_typed(
                connection_manager,
                "library_scan_started",
                {"directories": data.get('directories') or fallback_dirs},
            )
            return
        # Prefer the pre-counted total (#4616) — `total_found` is the running
        # discovery tally, which tracks `processed` in lockstep under the
        # streaming scan.
        total = (
            data.get('total_expected')
            or data.get('total_found', 0)
            or data.get('processed', 0)
        )
        processed = data.get('processed', 0)
        # Indeterminate unless the scanner supplies a real `progress` fraction
        # (#4411 / F4-04).
        pct = scan_progress_percentage(data)
        await broadcast_typed(
            connection_manager,
            "scan_progress",
            {
                "current": processed,
                "total": total,
                "percentage": pct,
                # Same policy as library_scan_started above (#4651): this path
                # lives under a user-chosen folder, and the frontend's
                # ScanStatusCard surfaces it verbatim in a tooltip by design.
                # The counting/discovering frames name a directory instead of a
                # file.
                "current_file": data.get('current_file') or data.get('file') or data.get('directory'),
                "phase": data.get('stage', 'processing'),
            },
        )

    def sync_progress(data: dict[str, Any]) -> None:
        # Runs on the scanner's worker thread. Schedule the broadcast on the
        # loop with a done-callback so a failure — a malformed `data` (#3864) or
        # a failed broadcast — is logged instead of silently dropped (#3512).
        # Broadcast errors are deliberately not suppressed for that reason.
        def _schedule() -> None:
            task = loop.create_task(_async_progress(data))
            task.add_done_callback(log_task_exception)
        loop.call_soon_threadsafe(_schedule)

    return sync_progress


def scan_complete_payload(scan_result: Any) -> ScanCompletePayload:
    """Canonical scan_complete payload (the frontend ScanCompleteMessage type).

    ``files_processed`` is the scanner's own count. The manual route used to
    report ``files_processed or files_found``, so a scan in which nothing was
    processed claimed every discovered file had been (#5912).
    """
    return {
        "files_processed": scan_result.files_processed if scan_result else 0,
        "files_added": scan_result.files_added if scan_result else 0,
        "files_updated": scan_result.files_updated if scan_result else 0,
        "files_skipped": scan_result.files_skipped if scan_result else 0,
        "files_failed": scan_result.files_failed if scan_result else 0,
        # #4841: name the failed files, not just the count.
        "failures": [
            cast(ScanFailurePayload, failure.to_dict())
            for failure in scan_result.failures
        ]
        if scan_result
        else [],
        "duration": scan_result.scan_time if scan_result else 0,
        "directories_scanned": scan_result.directories_scanned if scan_result else 0,
    }
