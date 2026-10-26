"""
Unhandled route exceptions still carry CORS and security headers (#5986)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``@app.exception_handler(Exception)`` runs on Starlette's outermost
``ServerErrorMiddleware``, so a route exception propagated past SecurityHeaders,
NoCache and CORS before the 500 was built: the response had no CSP, no
X-Frame-Options and no ``access-control-allow-origin``, and the traceback was
logged a second time when ``ServerErrorMiddleware`` re-raised.
``UnhandledExceptionMiddleware`` now answers inside the stack.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import sys
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.app import create_app  # noqa: E402
from config.middleware import setup_middleware  # noqa: E402


_ORIGIN = "http://127.0.0.1:8765"  # always allowed; 3000 is dev-only (#4350)


def _app():
    app = create_app()
    setup_middleware(app)

    @app.get("/api/_boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    return app


async def _get_boom() -> httpx.Response:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=_app(), raise_app_exceptions=False),
        base_url="http://localhost:8765",
    ) as client:
        return await client.get("/api/_boom", headers={"Origin": _ORIGIN})


@pytest.mark.asyncio
async def test_500_carries_cors_and_security_headers():
    response = await _get_boom()

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["access-control-allow-origin"] == _ORIGIN
    assert "default-src" in response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_unhandled_exception_is_logged_exactly_once(caplog):
    with caplog.at_level(logging.ERROR):
        await _get_boom()

    records = [r for r in caplog.records if "secret internal detail" in r.getMessage()]
    assert len(records) == 1
    assert records[0].exc_info is not None
