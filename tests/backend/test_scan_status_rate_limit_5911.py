"""GET /api/library/scan/status is not throttled by the scan POST limit (#5911).

The limiter matched `path.startswith("/api/library/scan")`, so the read-only
resync the frontend runs on every WebSocket (re)connect drew from the scan
POST's 2-per-minute rule. Its 429 was swallowed, leaving a missed terminal
frame (#4821) as a stuck "Scanning…" until the next reconnect.
"""

import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.limits import RATE_LIMIT_SCAN_MAX, RATE_LIMIT_SCAN_STATUS_MAX  # noqa: E402
from config.middleware import RateLimitMiddleware  # noqa: E402


def _app() -> FastAPI:
    app = FastAPI()

    @app.post("/api/library/scan")
    async def scan():
        return {"ok": True}

    @app.get("/api/library/scan/status")
    async def status():
        return {"scanning": False}

    app.add_middleware(RateLimitMiddleware)
    return app


@pytest.mark.asyncio
async def test_status_gets_beyond_the_scan_post_limit_all_succeed():
    count = RATE_LIMIT_SCAN_MAX + 3
    assert RATE_LIMIT_SCAN_STATUS_MAX >= count

    async with httpx.AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        codes = [(await client.get("/api/library/scan/status")).status_code for _ in range(count)]

    assert codes == [200] * count


@pytest.mark.asyncio
async def test_status_polling_does_not_drain_the_scan_post_budget():
    async with httpx.AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        for _ in range(RATE_LIMIT_SCAN_MAX + 3):
            await client.get("/api/library/scan/status")
        codes = [(await client.post("/api/library/scan")).status_code for _ in range(RATE_LIMIT_SCAN_MAX)]

    assert codes == [200] * RATE_LIMIT_SCAN_MAX


@pytest.mark.asyncio
async def test_scan_post_is_still_limited():
    async with httpx.AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        codes = [(await client.post("/api/library/scan")).status_code for _ in range(RATE_LIMIT_SCAN_MAX + 1)]

    assert codes[-1] == 429


@pytest.mark.asyncio
async def test_status_is_still_bounded():
    async with httpx.AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        codes = [
            (await client.get("/api/library/scan/status")).status_code
            for _ in range(RATE_LIMIT_SCAN_STATUS_MAX + 1)
        ]

    assert codes[-1] == 429
