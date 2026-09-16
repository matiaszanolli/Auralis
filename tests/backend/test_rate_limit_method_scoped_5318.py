"""
RateLimitMiddleware buckets are per-method, not just per-prefix (#5318)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``RateLimitMiddleware`` keyed its sliding-window bucket on
``client_ip:matched_prefix`` alone. ``OriginCheckMiddleware`` only gates
POST/PUT/DELETE/PATCH, so a read-only GET under a rate-limited prefix (e.g.
``GET /api/library/scan/status``) needs no trusted Origin and never triggers
a CORS preflight — an unauthenticated cross-origin page could flood it and
exhaust the budget the guarded state-changing POST relies on, since both
methods shared one bucket.

Fixed by folding the HTTP method into the bucket key, so GET and POST under
the same prefix are tracked independently: a GET flood can no longer starve
a sibling POST's budget (or vice versa), while a route that is itself
legitimately rate-limited as a GET (e.g. the similarity-query route
protected since #4728) keeps its own working limit.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
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


def _app_with_scan_routes() -> FastAPI:
    app = FastAPI()

    @app.get("/api/library/scan/status")
    async def scan_status():
        return {"scanning": False}

    @app.post("/api/library/scan")
    async def scan():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)
    return app


@pytest.mark.asyncio
async def test_cross_origin_get_flood_does_not_exhaust_the_post_budget():
    """AC: a GET flood on a sibling read-only route must not rate-limit the
    guarded state-changing POST under the same prefix (/api/library/scan is
    2 requests/60s)."""
    app = _app_with_scan_routes()
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Flood the GET route well past the shared rule's 2/60s budget — its
        # own bucket saturates, which is expected (the rule still applies
        # per-method), but this must not touch the POST route's bucket.
        get_responses = [await client.get("/api/library/scan/status") for _ in range(10)]
        # The POST route's own budget must still be fully available.
        post_responses = [await client.post("/api/library/scan") for _ in range(2)]

    assert any(r.status_code == 429 for r in get_responses), (
        "sanity check: the GET flood should exhaust its own bucket"
    )
    assert all(r.status_code == 200 for r in post_responses), (
        "the GET flood above starved the POST's own rate-limit budget (#5318)"
    )


@pytest.mark.asyncio
async def test_post_flood_does_not_exhaust_a_sibling_gets_budget():
    """Symmetric case: a POST flood must not consume the GET route's budget."""
    app = _app_with_scan_routes()
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        post_responses = [await client.post("/api/library/scan") for _ in range(2)]
        assert all(r.status_code == 200 for r in post_responses)
        # POST budget (2/60s) is now exhausted; a GET under the same prefix
        # must still get its own, unaffected budget.
        get_response = await client.get("/api/library/scan/status")

    assert get_response.status_code == 200


@pytest.mark.asyncio
async def test_each_state_changing_methods_budget_still_applies_to_itself():
    """The fix must not accidentally exempt POST from its own limit."""
    app = _app_with_scan_routes()
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = [await client.post("/api/library/scan") for _ in range(3)]

    assert sum(1 for r in responses if r.status_code == 200) == 2
    assert sum(1 for r in responses if r.status_code == 429) == 1
