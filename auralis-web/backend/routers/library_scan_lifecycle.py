"""
Scan lifecycle: client-disconnect watching and the bounded wait for the scanner thread (split from library_scan.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from fastapi import Request
from services.scanner_stop import stop_scanner
from typing import Any
import asyncio
import contextlib

logger = logging.getLogger(__name__)


# Nginx's convention for "client closed the request". Nothing can read this
# response — by definition the client is gone — but the status keeps the
# handler's exit honest in logs and tests instead of reporting a scan that
# "succeeded" or a 500 that never happened.
HTTP_CLIENT_CLOSED_REQUEST = 499


class ScanClientGone(Exception):
    """The client that requested the scan disconnected mid-scan (#4820)."""


async def _watch_for_disconnect(http_request: Request) -> None:
    """Return once the ASGI server reports the requesting client is gone.

    Blocks on the receive channel instead of polling ``is_disconnected()``,
    which does NOT work in this app: that helper peeks at the channel from an
    already-cancelled anyio scope, and every one of our BaseHTTPMiddleware
    layers (rate limit, security headers, no-cache, origin check) wraps
    ``receive`` in a task group whose exit swallows the message under that
    cancellation — so it answers "still connected" forever no matter what the
    client does. Verified against starlette 1.3.1 with the real stack: polling
    never fires, awaiting the channel fires in one round trip. Awaiting is also
    event-driven, so there is no poll interval to trade off.

    The request body was parsed into LibraryScanRequest before the handler ran,
    so ``http.disconnect`` is the only message left on the channel.
    """
    while True:
        try:
            message = await http_request.receive()
        except Exception:  # noqa: BLE001 - a broken channel must not kill the scan
            logger.debug("Disconnect watch failed; leaving the scan running", exc_info=True)
            # Report nothing rather than a false disconnect: park until the
            # caller cancels this watcher.
            await asyncio.Event().wait()
        else:
            if message.get("type") == "http.disconnect":
                return


async def _await_scan(
    scan_future: "asyncio.Future[Any]",
    scanner: Any,
    http_request: Request | None,
    timeout: float,
) -> Any:
    """Await the scanner thread, stopping it if the request ends early.

    Four outcomes, and every early one has to reach the scanner *thread*:

    * the scan finishes -> its ScanResult is returned;
    * the request task is cancelled (server shutdown) -> re-raised after
      stop_scan();
    * the scan exceeds ``timeout`` -> ``TimeoutError``;
    * the client disconnects -> ``ScanClientGone``. Closing a fetch does not
      cancel an already-scheduled Starlette route coroutine, so the handler
      has to watch the receive channel itself (#4820).

    The watcher is always cancelled and awaited before returning, so a scan
    that completes normally leaves no orphaned task behind.
    """
    watcher: asyncio.Task[None] | None = None
    if http_request is not None:
        watcher = asyncio.ensure_future(_watch_for_disconnect(http_request))
    try:
        waiters: set[Any] = {scan_future}
        if watcher is not None:
            waiters.add(watcher)
        try:
            done, _pending = await asyncio.wait(
                waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            await stop_scanner(scanner, scan_future)
            raise

        if scan_future in done:
            return scan_future.result()

        # Nothing else can leave that wait with the scan still running.
        await stop_scanner(scanner, scan_future)
        if watcher is not None and watcher in done:
            raise ScanClientGone()
        raise TimeoutError()
    finally:
        if watcher is not None and not watcher.done():
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher
