"""
CORS preflight allows the X-Confirm-Reset header (#5989)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The frontend sends ``X-Confirm-Reset: RESET`` on ``POST /api/library/reset`` and
the router rejects the call without it, but the CORS allow-list omitted it, so
the preflight from an allowed cross-origin page (e.g. 127.0.0.1:8765 calling
localhost:8765) failed with ``400 Disallowed CORS headers``.

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

from config.middleware import setup_middleware  # noqa: E402

_ORIGIN = "http://127.0.0.1:8765"


async def _preflight(request_headers: str) -> httpx.Response:
    app = FastAPI()
    setup_middleware(app)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:8765"
    ) as client:
        return await client.options(
            "/api/library/reset",
            headers={
                "Origin": _ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": request_headers,
            },
        )


@pytest.mark.asyncio
async def test_preflight_for_x_confirm_reset_is_allowed():
    response = await _preflight("content-type,x-confirm-reset")

    assert response.status_code == 200
    assert "x-confirm-reset" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.asyncio
async def test_unlisted_header_is_still_rejected():
    response = await _preflight("content-type,x-not-allowed")

    assert response.status_code == 400
