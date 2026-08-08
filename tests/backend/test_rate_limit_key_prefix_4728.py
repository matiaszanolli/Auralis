"""
Regression: RateLimitMiddleware keys on the matched prefix, not the full
path (#4728)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

RateLimitMiddleware matched a rule by path PREFIX but built its sliding-
window bucket key from the full concrete request path. Every rate-limited
prefix except two fixed paths (/api/files/upload, /api/library/scan) fans
out over a path parameter, so every distinct resource id got its own fresh,
effectively-unlimited budget — the docstring's stated contract ("20
similarity queries per minute") was not what the code enforced. 78
consecutive requests across 78 distinct track_ids against
/api/similarity/tracks/{id}/similar previously produced zero 429s.

Fixed by deriving the bucket key from the matched prefix captured during
the rule-matching loop, so all requests under one rule share one budget
regardless of how many distinct resource ids are touched.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.middleware import RateLimitMiddleware  # noqa: E402


def _app_with_similarity_routes() -> FastAPI:
    app = FastAPI()

    @app.get("/api/similarity/tracks/{track_id}/similar")
    async def similar(track_id: int):
        return {"track_id": track_id}

    app.add_middleware(RateLimitMiddleware)
    return app


@pytest.mark.asyncio
async def test_distinct_path_parameterized_resources_share_one_budget():
    """AC: N distinct ids under the same rule observe a 429 once the shared
    budget (20/60s for /api/similarity) is exhausted — not an unbounded
    per-id budget."""
    app = _app_with_similarity_routes()
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = [
            await client.get(f"/api/similarity/tracks/{track_id}/similar")
            for track_id in range(40)
        ]

    ok = sum(1 for r in responses if r.status_code == 200)
    limited = sum(1 for r in responses if r.status_code == 429)
    assert ok == 20, f"expected exactly the 20/60s budget to succeed, got {ok}"
    assert limited == 20, f"expected the remaining 20 requests to be rate-limited, got {limited}"
    # A 429 must appear well before request 40, per the issue's test plan.
    first_429_index = next(i for i, r in enumerate(responses) if r.status_code == 429)
    assert first_429_index < 40


@pytest.mark.asyncio
async def test_concurrent_distinct_ids_are_bounded_too():
    """Same invariant, but fired concurrently (asyncio.gather) rather than
    sequentially — matches the audit's empirical repro shape."""
    app = _app_with_similarity_routes()
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await asyncio.gather(
            *[
                client.get(f"/api/similarity/tracks/{track_id}/similar")
                for track_id in range(78)
            ]
        )

    ok = sum(1 for r in responses if r.status_code == 200)
    limited = sum(1 for r in responses if r.status_code == 429)
    assert ok == 20
    assert limited == 58


@pytest.mark.asyncio
async def test_process_and_upload_and_process_share_one_combined_budget():
    """AC: /api/processing/process and /api/processing/upload-and-process
    share a single combined budget (10/60s), not one each."""
    app = FastAPI()

    @app.post("/api/processing/process")
    async def process():
        return {"ok": True}

    @app.post("/api/processing/upload-and-process")
    async def upload_and_process():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = []
        for i in range(15):
            endpoint = "process" if i % 2 == 0 else "upload-and-process"
            responses.append(await client.post(f"/api/processing/{endpoint}"))

    ok = sum(1 for r in responses if r.status_code == 200)
    limited = sum(1 for r in responses if r.status_code == 429)
    assert ok == 10, f"expected the combined 10/60s budget across both routes, got {ok}"
    assert limited == 5


@pytest.mark.asyncio
async def test_unrelated_prefixes_still_have_independent_budgets():
    """The key must still separate distinct RULES from each other — only
    resources fanning out under the SAME rule should share a budget."""
    app = FastAPI()

    @app.post("/api/library/scan")
    async def scan():
        return {"ok": True}

    @app.get("/api/similarity/tracks/{track_id}/similar")
    async def similar(track_id: int):
        return {"track_id": track_id}

    app.add_middleware(RateLimitMiddleware)
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        scan_responses = [await client.post("/api/library/scan") for _ in range(3)]
        similarity_responses = [
            await client.get(f"/api/similarity/tracks/{i}/similar") for i in range(5)
        ]

    # /api/library/scan is 2/60s — exhausting it must not affect /api/similarity.
    assert sum(1 for r in scan_responses if r.status_code == 200) == 2
    assert sum(1 for r in scan_responses if r.status_code == 429) == 1
    assert all(r.status_code == 200 for r in similarity_responses)
