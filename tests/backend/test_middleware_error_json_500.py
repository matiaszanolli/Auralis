"""
Regression: exceptions inside a middleware dispatch return a JSON 500 (#4378)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

BaseHTTPMiddleware.dispatch runs outside FastAPI's ExceptionMiddleware, so a
raise inside NoCache / SecurityHeaders / RateLimit dispatch was handled by
Starlette's ServerErrorMiddleware and returned a plaintext "Internal Server
Error" without the {"detail": ...} shape the frontend expects. Each dispatch
now wraps its body in try/except and returns a uniform JSON 500.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.middleware import (
    NoCacheMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)


def _make_request(path: str = "/api/processing/foo") -> Request:
    """Minimal ASGI request scope sufficient for the middleware dispatches."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "query_string": b"",
    }
    return Request(scope)


async def _boom_call_next(request):
    raise RuntimeError("boom from downstream")


@pytest.mark.asyncio
@pytest.mark.parametrize("mw_cls", [
    NoCacheMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
])
async def test_dispatch_exception_returns_json_500(mw_cls):
    mw = mw_cls(app=MagicMock())
    # RateLimit only reaches call_next for a rate-limited prefix, so use one.
    request = _make_request("/api/processing/foo")

    response = await mw.dispatch(request, _boom_call_next)

    assert isinstance(response, JSONResponse)
    assert response.status_code == 500
    assert response.media_type == "application/json"
    body = json.loads(bytes(response.body))
    assert body == {"detail": "Internal server error"}


@pytest.mark.asyncio
async def test_non_raising_dispatch_still_passes_through():
    """A normal request must be unaffected by the new try/except wrapper."""
    from starlette.responses import PlainTextResponse

    async def ok_call_next(request):
        return PlainTextResponse("ok")

    mw = SecurityHeadersMiddleware(app=MagicMock())
    response = await mw.dispatch(_make_request("/index.html"), ok_call_next)

    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "DENY"
