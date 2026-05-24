"""
Regression tests for RateLimitMiddleware concurrent dispatch (#3329).

Pins the contract: concurrent requests from the same client must never
exceed the configured rate limit. Previously the get/prune/check/write
sequence on `_windows` had no explicit synchronization — safe in
single-threaded asyncio today, but a future await inserted in the block
would silently let extra requests slip through. The middleware now
serializes the critical section with an asyncio.Lock.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from config.middleware import RateLimitMiddleware


@pytest.fixture
def app_with_rate_limit():
    """Minimal FastAPI app with RateLimitMiddleware applied to /api/similarity."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/api/similarity")
    async def handler():
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_concurrent_requests_never_exceed_limit(app_with_rate_limit):
    """Fire 50 concurrent requests; exactly the configured max (20/min) should pass."""
    transport = ASGITransport(app=app_with_rate_limit)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = [client.get("/api/similarity") for _ in range(50)]
        responses = await asyncio.gather(*tasks)

    statuses = [r.status_code for r in responses]
    ok = sum(1 for s in statuses if s == 200)
    rate_limited = sum(1 for s in statuses if s == 429)

    # /api/similarity is configured as 20 requests / 60 seconds in
    # RateLimitMiddleware._RATE_LIMITS. The remaining 30 must be 429.
    assert ok == 20, f"Expected exactly 20 successful requests, got {ok} (statuses: {statuses})"
    assert rate_limited == 30, f"Expected exactly 30 rate-limited responses, got {rate_limited}"
    assert ok + rate_limited == 50  # No other status codes


@pytest.mark.asyncio
async def test_burst_then_burst_still_bounded(app_with_rate_limit):
    """Two back-to-back concurrent bursts must not accumulate past the limit."""
    transport = ASGITransport(app=app_with_rate_limit)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await asyncio.gather(*[client.get("/api/similarity") for _ in range(15)])
        second = await asyncio.gather(*[client.get("/api/similarity") for _ in range(15)])

    ok_total = sum(1 for r in (*first, *second) if r.status_code == 200)
    # 15 in the first burst all succeed (under the 20 limit).
    # The second burst hits the limit at the 6th request (15 + 5 = 20).
    assert ok_total == 20, f"Total successes across two bursts must be exactly 20, got {ok_total}"
