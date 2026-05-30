"""
Regression test: rate-limit 429 responses carry security headers (#3843)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

RateLimitMiddleware short-circuits with a 429 JSONResponse without calling
call_next. Because it was registered to run OUTSIDE SecurityHeadersMiddleware,
the 429 never received X-Content-Type-Options / X-Frame-Options / CSP / etc.
The fix reorders registration so SecurityHeaders (and NoCache) wrap RateLimit;
this test pins that a throttled response still carries the documented headers.

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

SECURITY_HEADERS = [
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
    "Permissions-Policy",
    "Content-Security-Policy",
]


@pytest.fixture
def app():
    application = FastAPI()
    setup_middleware(application)

    # /api/similarity is rate-limited to 20 requests / 60s.
    @application.get("/api/similarity")
    async def handler():
        return {"ok": True}

    return application


@pytest.mark.asyncio
async def test_429_response_has_security_headers(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Exhaust the 20/min budget, then one more to force a 429.
        last = None
        for _ in range(25):
            last = await client.get("/api/similarity")
            if last.status_code == 429:
                break

        assert last is not None and last.status_code == 429, (
            "Expected a 429 after exceeding the rate limit"
        )
        # The throttled response must still carry every security header.
        for header in SECURITY_HEADERS:
            assert header in last.headers, (
                f"429 response missing security header {header!r} — "
                "RateLimitMiddleware is short-circuiting outside SecurityHeadersMiddleware"
            )
        assert last.headers["X-Content-Type-Options"] == "nosniff"
        assert last.headers["X-Frame-Options"] == "DENY"
        # Retry-After from the rate limiter itself must still be present.
        assert "Retry-After" in last.headers


@pytest.mark.asyncio
async def test_200_response_still_has_security_headers(app):
    """Sanity: a normal 200 also carries the headers (no regression)."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/similarity")

    assert resp.status_code == 200
    for header in SECURITY_HEADERS:
        assert header in resp.headers
