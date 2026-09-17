"""
Scanner Stop
~~~~~~~~~~~~

Stops a library scan running in ``asyncio.to_thread``: signal the thread with
``stop_scan()``, then give it a bounded grace period to unwind.

Shared by the manual-scan endpoint (``routers/library_scan.py``) and the
auto-scanner (``services/library_auto_scanner.py``). Each used to carry its own
copy of this wait with a bare 5-second literal (#5196).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any

from core.env_config import get_int_env

logger = logging.getLogger(__name__)

# How long to wait for the scanner thread to notice stop_scan() and exit.
# Whole seconds; override via AURALIS_SCAN_STOP_GRACE_SECONDS, the inner
# counterpart of the manual scan's outer AURALIS_SCAN_TIMEOUT — see
# auralis-web/backend/CONFIG.md.
SCANNER_STOP_GRACE_SECONDS: float = float(get_int_env("AURALIS_SCAN_STOP_GRACE_SECONDS", 5))


async def stop_scanner(
    scanner: Any,
    scan_future: "asyncio.Future[Any]",
    *,
    label: str = "Scanner",
) -> None:
    """Signal the scanner thread to stop and give it a moment to unwind.

    #3710: cancelling the awaitable cannot interrupt ``asyncio.to_thread``;
    only ``stop_scan()`` reaches the thread, and only the thread can release
    the scan slot it holds.

    Never raises. A thread that outlives the grace period is logged and left to
    finish at its next checkpoint; a scan that fails while stopping is logged at
    debug, because the caller reports the scan's own outcome — and a caller
    unwinding a cancellation must still get to re-raise its ``CancelledError``.

    Args:
        scanner: The scanner whose ``stop_scan()`` signals the thread.
        scan_future: The ``asyncio.to_thread`` future running the scan.
        label: Names the caller in the timeout warning.
    """
    scanner.stop_scan()
    try:
        await asyncio.wait_for(
            asyncio.shield(scan_future), timeout=SCANNER_STOP_GRACE_SECONDS
        )
    except (TimeoutError, asyncio.CancelledError):
        logger.warning(
            "%s thread did not exit within %ss of stop_scan(); "
            "thread will continue in background until next checkpoint.",
            label,
            SCANNER_STOP_GRACE_SECONDS,
        )
    except Exception:  # noqa: BLE001 - the scan's own failure is reported by the caller
        logger.debug("%s thread raised while stopping", label, exc_info=True)
