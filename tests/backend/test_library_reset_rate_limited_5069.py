"""POST /api/library/reset is rate limited (#5069).

The destructive full-library reset was missing from the rate-limit table, so a looping client could invoke it
without bound. It now allows one call per window per client.
"""

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from config.middleware import RateLimitMiddleware


@pytest.mark.asyncio
async def test_a_second_reset_in_the_window_is_refused():
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.post("/api/library/reset")
    async def reset():
        return {"ok": True}

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/library/reset")
        second = await client.post("/api/library/reset")

    assert first.status_code == 200
    assert second.status_code == 429
