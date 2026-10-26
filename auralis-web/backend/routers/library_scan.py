"""
Library Scan Router
~~~~~~~~~~~~~~~~~~~~

Scan-domain endpoint: directory scan with async progress broadcast.

Endpoints:
- POST /api/library/scan - Scan directories and import audio files

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from schemas import LibraryScanRequest, ScanResultResponse

from services.missing_tracks import prune_missing_tracks
from services.scan_events import enqueue_added_for_fingerprinting, make_progress_callback

from .errors import LibraryUnavailableError, handle_query_error
from .library_scan_events import broadcast_scan_complete, broadcast_scan_error
from .library_scan_lifecycle import (
    HTTP_CLIENT_CLOSED_REQUEST,
    ScanClientGone,
    _await_scan,
)
from .library_scan_deps import (
    _LibraryScanDeps,
    _deps,
    _get_connection_manager,
    _get_library_database,
)

logger = logging.getLogger(__name__)


class ScanStatusResponse(BaseModel):
    """Live scan-slot state, for a client resyncing mid-scan (#4821)."""
    is_scanning: bool = Field(description="True while a directory scan holds the scan slot")


# ============================================================================
# DEPENDENCY WIRING (#5166, following the #4670 precedent set in player.py)
#
# create_library_scan_router() used to be a 256-line closure: both handlers
# below were nested inside it purely to reach get_library_database /
# connection_manager via closure capture, which made either one impossible to
# import or call without first building the whole router. Handlers are now
# module level; they reach the same objects through FastAPI Depends() instead.
#
# _LibraryScanDeps holds the raw callable/object one create_library_scan_router()
# call received. It is bound per router instance through RouterDeps
# (dependencies.py): a router-level dependency publishes it for the duration of
# a request, so a second factory call (several test files build their own scan
# router with stub dependencies) cannot repoint the live router at those stubs
# (#5262, #5762). It does NOT reproduce the #4361 module-level-`APIRouter()`
# hazard, since the router instance itself is built fresh, per call, inside the
# factory below.
#
# Both attributes default to None -- unlike player.py's _PlayerDeps, this
# factory's parameters are themselves optional, so "never populated" and
# "populated with None" have to behave identically (a bare annotation would
# raise AttributeError instead of resolving to None).
#
# A handler's Depends() default is only consulted when FastAPI itself invokes
# it for a real request; a direct unit-test call passes library_database /
# connection_manager explicitly as keyword arguments and never touches
# _LibraryScanDeps at all -- that's the seam #5166 asked for.
# ============================================================================


# ============================================================================
# SCAN ENDPOINTS
# ============================================================================

async def get_scan_status(
    library_database: Any = Depends(_get_library_database),
) -> dict[str, Any]:
    """Resync point for a client that (re)connects mid-scan or after one
    finished while its WebSocket was disconnected (#4821).

    Scan lifecycle (`library_scan_started`/`scan_progress`/`scan_complete`/
    `library_scan_error`) is otherwise broadcast-only — a client offline
    when the terminal frame goes out never learns the scan ended, and
    `isScanning` gets stuck. This is a live read of the same scan-slot
    counter try_acquire_scan_slot()/release_scan_slot() maintain, so it
    self-heals even after a scan crashed without emitting a terminal frame.
    """
    if library_database is None:
        raise LibraryUnavailableError()
    return {"is_scanning": library_database.is_scanning()}


async def scan_library(
    request: LibraryScanRequest,
    http_request: Request,
    library_database: Any = Depends(_get_library_database),
    connection_manager: Any = Depends(_get_connection_manager),
) -> ScanResultResponse:
    """Scan directories for audio files and add them to the library.

    Progress updates are broadcast via WebSocket (see WEBSOCKET_API.md).

    ``http_request`` is the raw ASGI request, taken alongside the parsed
    body purely so the scan can be stopped when the caller goes away
    (#4820) — see ``_await_scan``.
    """
    try:
        from auralis.library.scanner import LibraryScanner

        # Guard the *resolved* manager, not the getter: the getter is always
        # truthy, so the previous check never fired and a None manager
        # reached LibraryScanner as an opaque 500 (#4656).
        if library_database is None:
            raise LibraryUnavailableError()

        scanner = LibraryScanner(library_database)

        # NOTE: `library_scan_started` is NOT broadcast here (#4602). It used
        # to be sent unconditionally on entry — before scan_directories() ran
        # and long before `result.rejected` could be known — so a second scan
        # request that ended up 409'd had already told the UI a scan began,
        # and its handler resets every counter, destroying the live progress
        # of the scan actually running. The scanner now emits a
        # `stage: 'started'` progress event once it owns the scan slot, and
        # the callback below translates that into the frame (#2711's intent,
        # correctly ordered).

        if connection_manager:
            scanner.set_progress_callback(
                make_progress_callback(asyncio.get_running_loop(), connection_manager, request.directories)
            )

        scan_timeout = float(os.environ.get("AURALIS_SCAN_TIMEOUT", "3600"))
        # #3710: capture the to_thread future so we can signal the scanner
        # to stop on cancellation/timeout/disconnect — asyncio.wait_for
        # cancels the awaitable but cannot terminate the underlying thread
        # without this.
        scan_future = asyncio.ensure_future(asyncio.to_thread(
            scanner.scan_directories,
            directories=request.directories,
            recursive=request.recursive,
            skip_existing=request.skip_existing,
            check_modifications=True,
        ))
        result = await _await_scan(scan_future, scanner, http_request, scan_timeout)

        # Rejected scan (e.g., already in progress) — return 409 (#2870).
        if result.rejected:
            raise HTTPException(status_code=409, detail="Scan already in progress")

        await enqueue_added_for_fingerprinting(result.added_tracks)

        # #5458: prune tracks whose files are gone, exactly as the
        # auto-scanner does. Only it used to, so users with auto_scan off
        # (or rescanning by hand after moving files) kept dead entries.
        # Before scan_complete: useScanProgress counts a removal frame only
        # while the scan is still in progress. The count is folded into the
        # library_updated condition below (#5515) — a prune-only rescan
        # (files deleted on disk, none added/updated) must still refresh the
        # open library view, same as the auto-scanner's `files_added or
        # removed` guard.
        removed = await prune_missing_tracks(library_database, connection_manager)

        await broadcast_scan_complete(connection_manager, result, removed)

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

    except TimeoutError:
        # Terminal WS frame so a `library_scan_started`-driven UI leaves the
        # scanning state instead of hanging on "Scanning..." (#4413). Mirrors
        # the auto-scanner's error broadcast; no OS paths leak (#3543).
        await broadcast_scan_error(
            connection_manager, f"library scan timed out after {int(scan_timeout)}s"
        )
        raise HTTPException(status_code=504, detail=f"Library scan timed out after {scan_timeout}s")
    except ScanClientGone:
        # #4820: the frontend aborts this fetch on unmount and when a second
        # scan supersedes it. That abort used to reach nothing — the handler
        # took only the parsed body, so it could not observe
        # `is_disconnected()`, and a closed fetch does not cancel an
        # already-scheduled route coroutine. The scan ran to completion (or
        # its 1-hour timeout) holding the scan slot, 409-ing every new scan
        # the user started. `_await_scan` now stops the scanner thread, which
        # releases the slot on its way out.
        #
        # Same terminal frame as cancellation below: the WebSocket normally
        # outlives the aborted fetch, so the UI still has to be told to leave
        # the scanning state.
        await broadcast_scan_error(connection_manager, "library scan cancelled")
        raise HTTPException(
            status_code=HTTP_CLIENT_CLOSED_REQUEST,
            detail="Client disconnected; library scan stopped",
        )
    except asyncio.CancelledError:
        # The one exit #4413 missed. Since Python 3.8 CancelledError derives
        # from BaseException, so `except Exception` below never caught it and
        # there was no `finally` — the handler simply left, with no terminal
        # frame. `useScanProgress` clears `isScanning` only on scan_complete
        # or library_scan_error, so the panel stayed on "Scanning…" for the
        # rest of the session with tracks half-imported, recoverable only by
        # a page reload. Genuine cancellation of this task means server
        # shutdown; the frontend's unmount/supersede aborts surface as
        # ScanClientGone above (#4820), not as cancellation.
        #
        # Must be ordered before `except Exception` (which cannot catch it
        # anyway) and kept separate from the `except (TimeoutError,
        # CancelledError)` at the wait_for above, which re-raises
        # deliberately after stop_scan(). TimeoutError still reaches its own
        # handler above: it is an Exception subclass, not this one.
        await broadcast_scan_error(connection_manager, "library scan cancelled")
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
        # 500 also releases the scanning state (#4413). Unlike
        # library_scan_started/scan_progress above, `str(e)` here can name
        # ANY path the exception happened to touch — not just the
        # directories the user chose — so this frame stays redacted even
        # though those two intentionally are not (#4651).
        await broadcast_scan_error(
            connection_manager, f"{type(e).__name__} during library scan"
        )
        raise handle_query_error("scan library", e)


def create_library_scan_router(
    get_library_database: Callable[[], Any] | None = None,
    connection_manager: Any | None = None,
) -> APIRouter:
    """Factory: library scan routes."""
    deps = _LibraryScanDeps(get_library_database, connection_manager)

    router = APIRouter(tags=["library"], dependencies=[Depends(_deps.bind(deps))])
    router.add_api_route(
        "/api/library/scan/status",
        get_scan_status,
        methods=["GET"],
        response_model=ScanStatusResponse,
    )
    router.add_api_route(
        "/api/library/scan",
        scan_library,
        methods=["POST"],
        response_model=ScanResultResponse,
    )
    return router
