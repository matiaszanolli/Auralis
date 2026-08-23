"""
Integration regression: a route handler's unhandled exception reaches
config/app.py's registered @app.exception_handler(Exception), not whichever
middleware happens to be innermost (#4808)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Builds a minimal app with the real middleware stack (setup_middleware) and
the same shape of registered Exception handler config/app.py installs, then
drives a deliberately-raising route through the full stack -- the issue's own
"Unit test" ask. Before the fix, RateLimitMiddleware's `except Exception`
around `call_next(request)` caught this before it ever reached the handler;
the client-visible response was identical either way (both produce
{"detail": "Internal server error"} / 500), so this test asserts on the
mechanism (which log message fired, with what method/path), not just the
response body.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.middleware import setup_middleware

logger = logging.getLogger("config.app")


@pytest.fixture
def app():
    application = FastAPI()
    setup_middleware(application)

    # Same shape as config/app.py's registered handler -- see
    # config/app.py::unhandled_exception_handler.
    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: {exc}",
            exc_info=True,
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @application.get("/api/processing/boom")
    async def boom():
        raise RuntimeError("deliberate route-handler failure")

    return application


@pytest.mark.asyncio
async def test_route_exception_is_logged_by_the_registered_handler_not_a_middleware(app, caplog):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    with caplog.at_level(logging.ERROR):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/processing/boom", headers={"Origin": "http://localhost:8765"}
            )

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}

    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "Unhandled exception on GET /api/processing/boom" in m for m in messages
    ), f"expected the registered handler's log line, got: {messages}"
    assert not any(
        "Unhandled exception in RateLimitMiddleware" in m for m in messages
    ), "route exception was caught (and misattributed) by RateLimitMiddleware again"
    assert not any(
        "Unhandled exception in " in m and "RateLimitMiddleware" not in m and "Unhandled exception on" not in m
        for m in messages
    ), f"route exception was misattributed to some other middleware: {messages}"


@pytest.mark.asyncio
async def test_non_rate_limited_path_also_propagates_correctly(app, caplog):
    """The same guard on a path with no rate-limit rule at all -- confirms
    the fix isn't accidentally specific to rate-limited prefixes."""

    @app.get("/unrated/boom")
    async def unrated_boom():
        raise RuntimeError("deliberate failure on an unrated path")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    with caplog.at_level(logging.ERROR):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/unrated/boom")

    assert resp.status_code == 500
    messages = [r.getMessage() for r in caplog.records]
    assert any("Unhandled exception on GET /unrated/boom" in m for m in messages)
