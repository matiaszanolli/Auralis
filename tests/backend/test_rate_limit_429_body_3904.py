"""
Regression: the 429 body identifies which rule fired (#3904)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

RateLimitMiddleware's 429 response used to be a generic
`{"detail": "Too many requests"}` with only a `Retry-After` header. The
frontend had no programmatic signal of which limit (upload vs scan vs
similarity) was hit and had to parse the header / guess from the request
path to show a specific message ("you're scanning too often, wait 23s").

The middleware already knows both the matched rule prefix and the
retry-after duration when it builds the response, so both are now included
in the JSON body too.

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

from config.middleware import RateLimitMiddleware  # noqa: E402


def _app_with_scan_route() -> FastAPI:
    app = FastAPI()

    @app.post("/api/library/scan")
    async def scan():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)
    return app


@pytest.mark.asyncio
async def test_429_body_names_the_matched_rule_and_retry_after():
    app = _app_with_scan_route()
    transport = ASGITransport(app=app)

    from config.limits import RATE_LIMIT_SCAN_MAX

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = [
            await client.post("/api/library/scan")
            for _ in range(RATE_LIMIT_SCAN_MAX + 1)
        ]

    limited = [r for r in responses if r.status_code == 429]
    assert limited, "expected at least one 429 within the scan rule's budget + 1"

    body = limited[0].json()
    assert body["detail"] == "Too many requests"
    # The matched rule prefix, not the concrete request path.
    assert body["rule"] == "/api/library/scan"
    # Same duration as the Retry-After header, available in the body too so
    # the frontend doesn't have to parse the header.
    header_retry_after = int(limited[0].headers["Retry-After"])
    assert body["retry_after_seconds"] == header_retry_after
    assert body["retry_after_seconds"] > 0
