"""
Regression test: state-changing REST requests require a trusted Origin (#4893)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CORS blocks a hostile page's JavaScript from *reading* a cross-origin response,
but "simple requests" (POST/PUT/DELETE with no body, or a CORS-safelisted
Content-Type) never trigger a preflight and still execute server-side. Any
state-changing REST route whose input comes entirely from the URL path/query
was exploitable blind via a hidden auto-submitting form or
`navigator.sendBeacon()`. OriginCheckMiddleware closes this the same way
ConnectionManager.connect already does for WebSocket upgrades.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.middleware import setup_middleware

TRUSTED_ORIGIN = "http://localhost:8765"
UNTRUSTED_ORIGIN = "https://evil.example"


@pytest.fixture
def app():
    application = FastAPI()
    setup_middleware(application)

    @application.post("/api/player/queue/clear")
    async def clear_queue():
        return {"ok": True}

    @application.put("/api/settings")
    async def update_settings():
        return {"ok": True}

    @application.get("/api/player/status")
    async def status():
        return {"ok": True}

    return application


@pytest.mark.asyncio
async def test_untrusted_origin_is_rejected(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/player/queue/clear", headers={"Origin": UNTRUSTED_ORIGIN})

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trusted_origin_is_allowed(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/player/queue/clear", headers={"Origin": TRUSTED_ORIGIN})

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_no_origin_from_loopback_is_allowed(app):
    """Non-browser clients (the app's own frontend process, curl, tests) send
    no Origin header at all; httpx's ASGITransport client is loopback by
    default and must not be broken by this middleware."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/player/queue/clear")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_no_origin_from_non_loopback_is_rejected(app):
    """#5089's regression test: a non-browser client with no Origin header,
    reported from a non-loopback host, must still be rejected.

    This is the exact shape of every request Starlette's own `TestClient`
    sends — it reports its client host as the non-loopback literal
    'testclient' — which is what let 131 tests across 10 files silently pass
    a 403 instead of exercising the route/handler they meant to test until
    the shared `tests/backend/conftest.py::client` fixture started sending a
    trusted Origin by default. This test covers the rejection path itself so
    it doesn't go untested in the other direction now that the fixture no
    longer exercises it.
    """
    transport = ASGITransport(app=app, client=("203.0.113.5", 12345))  # TEST-NET-3, RFC 5737
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/player/queue/clear")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_untrusted_origin_rejected_on_put(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put("/api/settings", headers={"Origin": UNTRUSTED_ORIGIN})

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_requests_are_not_checked(app):
    """GET carries no state-changing risk and is not subject to this check —
    a hostile page reading the response is already blocked by CORS itself."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/player/status", headers={"Origin": UNTRUSTED_ORIGIN})

    assert resp.status_code == 200
