"""
Library-scan WebSocket frames and post-scan steps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The progress bridge, fingerprint enqueue and terminal frames that
``scan_library`` used to inline (split from library_scan.py, #5831). The frame
payload policy (#4651: redact only what the user did not supply) is unchanged.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, cast

from helpers import scan_progress_percentage
from websocket.outbound.library import ScanCompletePayload, ScanFailurePayload
from websocket.outbound_messages import broadcast_typed

logger = logging.getLogger(__name__)


def make_progress_callback(
    connection_manager: Any, directories: list[str]
) -> Callable[[dict[str, Any]], None]:
    """Build the scanner progress callback that bridges the sync scanner thread
    to async WebSocket broadcasts.

    asyncio.to_thread runs the scanner in a worker thread, so the callback
    schedules each broadcast on the running loop with run_coroutine_threadsafe.
    ``directories`` is the fallback for the ``library_scan_started`` frame.
    """
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
                # `directories` is the resolved-absolute form of
                # what the requesting user picked via a directory
                # dialog (LibraryScanRequest.validate_directory_paths) —
                # a value the user already knows, not a path the
                # server introduced. Deliberately NOT class-name
                # redacted like library_scan_error below: that frame
                # echoes an *unhandled exception's message*, which
                # can name server-internal paths the user never
                # chose — a different, broader disclosure surface.
                # One policy for the whole scan-frame family (#4651):
                # redact only what the user did not themselves supply.
                asyncio.run_coroutine_threadsafe(
                    broadcast_typed(
                        connection_manager,
                        "library_scan_started",
                        {
                            "directories": progress_data.get('directories')
                            or directories,
                        },
                    ),
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
                broadcast_typed(
                    connection_manager,
                    "scan_progress",
                    {
                        "current": processed,
                        "total": total,
                        "percentage": percentage,
                        # Same policy as library_scan_started above
                        # (#4651): this path lives under a directory
                        # the user picked, and the frontend's
                        # ScanStatusCard surfaces it verbatim in a
                        # tooltip by design — redacting it here
                        # would silently break that affordance.
                        "current_file": progress_data.get('current_file') or progress_data.get('file'),
                        "phase": stage,
                    },
                ),
                loop,
            )
        except Exception:
            logger.warning(
                "scan_library progress callback failed — malformed progress_data",
                exc_info=True,
            )

    return _progress_callback


async def enqueue_added_for_fingerprinting(added_tracks: list[Any]) -> None:
    """Enqueue newly added tracks for background fingerprinting (#2382).

    Failures are logged, never raised: fingerprinting is a follow-up, not part
    of the scan's success.
    """
    if not added_tracks:
        return
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
                return sum(1 for t in added_tracks if fp_queue.enqueue(t.id))

            enqueued = await asyncio.to_thread(_enqueue_added)
            if enqueued:
                logger.info(f"Enqueued {enqueued} tracks for fingerprinting after scan")
    except Exception as fp_err:
        logger.warning(f"Fingerprint enqueue failed after scan: {fp_err}")


async def broadcast_scan_complete(
    connection_manager: Any, result: Any, removed: Any
) -> None:
    """Broadcast ``scan_complete`` and, if anything changed, ``library_updated``.

    Field shape matches ScanCompleteMessage and the auto-scanner path
    (services/library_auto_scanner.py, fixes #3502).
    """
    if not connection_manager:
        return
    scan_complete_payload: ScanCompletePayload = {
        "files_processed": result.files_processed or result.files_found,
        "files_added": result.files_added,
        "files_updated": result.files_updated,
        "files_skipped": result.files_skipped,
        "files_failed": result.files_failed,
        # #4841: name the failed files, not just the count.
        "failures": [
            cast(ScanFailurePayload, failure.to_dict())
            for failure in result.failures
        ],
        "duration": result.scan_time,
        "directories_scanned": result.directories_scanned,
    }
    await broadcast_typed(
        connection_manager,
        "scan_complete",
        scan_complete_payload,
    )
    if result.files_added or result.files_updated or removed:
        await broadcast_typed(
            connection_manager,
            "library_updated",
            # Fields here must match LibraryUpdatedMessage in
            # frontend/src/types/ws/library.ts.
            {
                "action": "scan",
                "track_count": result.files_added,
            },
        )


async def broadcast_scan_error(connection_manager: Any, message: str) -> None:
    """Terminal ``library_scan_error`` frame, so a ``library_scan_started``-driven
    UI leaves the scanning state (#4413). Callers pass messages that name no
    server paths (#3543, #4651)."""
    if connection_manager:
        await broadcast_typed(connection_manager, "library_scan_error", {"error": message})
