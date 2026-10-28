"""
Catch-all routes and frontend serving for main.py (split from main.py, #5834).

Registration ORDER matters and is the caller's job: ``register_fallback_routes``
must run after ``setup_routers`` (so the real ``/ws`` and ``/api`` routes match
first, Starlette checking routes in registration order) and before
``mount_frontend`` (whose ``StaticFiles`` Mount at ``/`` matches every path).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette import status
from starlette.routing import Match

from .app import is_dev_mode

logger = logging.getLogger(__name__)

# Body for the `/` fallback when the built frontend is missing.
#
# Deliberately free of `frontend_path` (#4351). The old version interpolated it
# — HTML-escaped, so never an XSS vector, but it handed any client that can
# reach `/` the install layout: the PyInstaller _MEIPASS temp dir, or
# /home/<user>/... which also discloses the OS username. A stray browser tab or
# a DNS-rebound page could read it.
#
# The path is still available for diagnostics from the logger.debug calls, which
# is where #4366 put absolute paths so INFO-level output stays safe to paste
# into a public bug report. Kept a module-level constant rather than inlined so
# the branch is reachable from a test: which `/` handler gets registered is
# decided at import time by conditions a test cannot easily force.
FRONTEND_MISSING_HTML = """
        <html>
            <head><title>Auralis Web</title></head>
            <body>
                <h1>🎵 Auralis Web Backend</h1>
                <p>FastAPI backend is running!</p>
                <p>Frontend assets not found — the installation looks incomplete.
                   Reinstall Auralis, or run the backend with --dev and serve the
                   frontend with Vite.</p>
            </body>
        </html>
        """

# Named so _methods_allowed_for can skip them. Both match *every* path, so
# leaving them in would report each path as allowing every method: the
# catch-all matches its own request, and the SPA Mount is what shadowed the 405
# in the first place.
_CATCH_ALL_ROUTE_NAMES = {"_unmatched_api_path", "frontend"}

_PROBE_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")


def _methods_allowed_for(request: Request) -> set[str]:
    """Methods some real route accepts for this request's path.

    Empty when no route matches the path under any method — a genuine 404
    rather than a method mismatch.

    Probes each method through Starlette's own matcher rather than reading
    `route.methods`: `app.include_router()` leaves each router as a single
    nested `_IncludedRouter` entry in `app.routes` (children are not flattened
    up), and those expose no `.methods` — so a direct attribute read finds no
    API routes at all and every path looks like a 404. Asking `matches()` for a
    FULL match per candidate method delegates to the same resolution the real
    request would use, at any nesting depth.
    """
    allowed: set[str] = set()
    probe = dict(request.scope)
    for method in _PROBE_METHODS:
        probe["method"] = method
        for route in request.app.routes:
            if getattr(route, "name", None) in _CATCH_ALL_ROUTE_NAMES:
                continue
            if route.matches(probe)[0] is Match.FULL:
                allowed.add(method)
                break
    return allowed


async def _unregistered_websocket(websocket: WebSocket) -> None:
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


async def _unmatched_api_path(request: Request, path: str) -> JSONResponse:
    allowed = _methods_allowed_for(request)
    if allowed:
        return JSONResponse(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            content={"detail": "Method Not Allowed"},
            headers={"Allow": ", ".join(sorted(allowed))},
        )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Not Found"},
    )


def register_fallback_routes(app: FastAPI) -> None:
    """Register the catch-alls for unregistered WebSocket and unmatched /api paths."""
    # Catch-all for unregistered WebSocket paths (#4800). Starlette's Mount
    # matches websocket scopes just like http ones (it only special-cases the
    # path, not scope["type"]), so without this a client that upgrades to any
    # unregistered /ws* path in production falls through the single real /ws
    # route all the way to the StaticFiles Mount, whose __call__ asserts
    # scope["type"] == "http" and raises an unhandled AssertionError instead of
    # a clean close. Registered after the real /ws route, so /ws itself still
    # matches first and every other path gets a clean policy-violation close.
    app.add_api_websocket_route("/{path:path}", _unregistered_websocket)

    # Catch-all for unmatched /api paths (#5090). Same placement rationale as the
    # WebSocket catch-all above.
    #
    # Starlette returns 405 for a method mismatch only when NO route fully matches
    # the request. The SPA Mount at "/" fully matches *every* path, so once it
    # is registered it beats the partial (path-matched, method-mismatched) match on
    # every real API route — `GET /api/files/upload` reached StaticFiles, found no
    # such file on disk, and became a 404 instead of the 405 the route shape
    # implies. That also meant every unknown /api path returned StaticFiles' error
    # rather than the app's JSON error shape.
    #
    # Because the mount only exists in production with a built frontend, and
    # `auralis-web/frontend/dist/` is gitignored and never built by
    # `backend-tests.yml`, this silently made behaviour differ between CI (no
    # mount, 405) and a developer machine that had run a frontend build (mount,
    # 404). Handling /api explicitly here makes the response identical in both,
    # and keeps API errors in the API's own format.
    app.add_api_route(
        "/api/{path:path}",
        _unmatched_api_path,
        methods=list(_PROBE_METHODS),
        include_in_schema=False,
    )


def resolve_frontend_path(backend_dir: Path) -> Path:
    """Where the built frontend lives for the current execution context."""
    if os.environ.get('ELECTRON_MODE') == '1':
        # Running inside Electron (frozen binary or script)
        # Frontend is in resources/frontend alongside resources/backend
        frontend_path = Path(os.getcwd()).parent / "frontend"
        if not frontend_path.exists():
            # Fallback: resolve relative to this script
            frontend_path = backend_dir.resolve().parent / "frontend"
        logger.info("Electron mode: looking for frontend")
    elif hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
        # PyInstaller bundle but not Electron - frontend might be bundled
        meipass = getattr(sys, '_MEIPASS')
        frontend_path = Path(meipass) / "frontend"
        logger.info("PyInstaller mode: frontend bundled with _MEIPASS")
    else:
        # Development mode - look in regular location
        frontend_path = backend_dir.parent / "frontend" / "dist"

    # Absolute path (embeds OS username + install layout) kept at DEBUG only;
    # INFO stays free of it so it's safe to paste into a public bug report (#4366).
    logger.debug(f"Looking for frontend at: {frontend_path}")
    return frontend_path


def mount_frontend(app: FastAPI, backend_dir: Path) -> None:
    """Serve the built frontend (production) or a stub page at ``/``."""
    frontend_path = resolve_frontend_path(backend_dir)

    # Only mount static files in production (when not running --dev)
    # In development, Vite serves the frontend and proxies API requests
    # StaticFiles mount at "/" interferes with WebSocket routes, so we must avoid it in dev mode
    dev_mode = is_dev_mode()  # once: env-var activation logs a warning each call
    if not dev_mode and frontend_path.exists():
        logger.info("✅ Serving frontend (production mode)")
        logger.debug(f"Serving frontend from: {frontend_path}")
        app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
    elif dev_mode:
        logger.info("ℹ️  Development mode: Vite serves frontend, StaticFiles NOT mounted (preserves WebSocket routes)")

        @app.get("/")
        async def root() -> HTMLResponse:
            return HTMLResponse("""
        <html>
            <head><title>Auralis Web</title></head>
            <body>
                <h1>🎵 Auralis Web Backend</h1>
                <p>Backend API is running!</p>
                <p>Frontend served by Vite on http://localhost:3000+</p>
                <p><a href="/api/docs">View API Documentation</a></p>
            </body>
        </html>
        """)
    else:
        logger.warning("⚠️  Frontend not found — check installation")
        logger.debug(f"Frontend not found at: {frontend_path}")

        @app.get("/")
        async def root() -> HTMLResponse:
            return HTMLResponse(FRONTEND_MISSING_HTML)
