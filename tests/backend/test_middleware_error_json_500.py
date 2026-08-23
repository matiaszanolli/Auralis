"""
Middleware error handling: own-logic errors get a JSON 500, downstream
route-handler exceptions propagate to the registered handler (#4378, #4808)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#4378 wrapped each middleware's whole dispatch body (including
`call_next(request)`) in try/except so a raise wouldn't fall through to
Starlette's ServerErrorMiddleware without the {"detail": ...} JSON shape the
frontend expects.

#4808 found the collateral damage: `BaseHTTPMiddleware.call_next` re-raises a
downstream route handler's own exception at its call site, so wrapping
call_next in the SAME try caught every unhandled route exception too and
misattributed it as e.g. "Unhandled exception in RateLimitMiddleware" --
config/app.py's registered `@app.exception_handler(Exception)` never fired,
and its `request.method`/`request.url.path` logging never ran for route-level
exceptions. Since that registered handler produces the identical
{"detail": "Internal server error"} / 500 shape #4378 was chasing, the fix
narrows each middleware's try to its own logic only, with `call_next`
outside it.

These tests now assert BOTH halves: a downstream exception propagates
unmodified (this file's central regression guard), and each middleware's own
internal-logic failure still gets the JSON 500 #4378 wanted.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.middleware import (
    NoCacheMiddleware,
    OriginCheckMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)

pytestmark = pytest.mark.asyncio


def _make_request(path: str = "/api/processing/foo", method: str = "GET") -> Request:
    """Minimal ASGI request scope sufficient for the middleware dispatches."""
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(b"origin", b"http://127.0.0.1:8765")],
        "client": ("127.0.0.1", 12345),
        "query_string": b"",
    }
    return Request(scope)


async def _boom_call_next(request):
    raise RuntimeError("boom from downstream")


async def _ok_call_next(request):
    return PlainTextResponse("ok")


class TestDownstreamExceptionsPropagate:
    """The #4808 regression guard: a route handler's exception must reach
    config/app.py's registered Exception handler, not be swallowed and
    misattributed by whichever middleware happened to be innermost."""

    @pytest.mark.parametrize("mw_cls", [
        NoCacheMiddleware,
        SecurityHeadersMiddleware,
        RateLimitMiddleware,
        OriginCheckMiddleware,
    ])
    async def test_call_next_exception_is_not_caught(self, mw_cls):
        mw = mw_cls(app=MagicMock())
        # RateLimitMiddleware only reaches call_next for GET on any path (not
        # rate-limited) or after its own bookkeeping on a limited prefix --
        # either way call_next still runs. OriginCheckMiddleware only guards
        # state-changing /api methods, so GET reaches call_next unconditionally
        # for it too.
        request = _make_request("/api/processing/foo", method="GET")

        with pytest.raises(RuntimeError, match="boom from downstream"):
            await mw.dispatch(request, _boom_call_next)


class TestOwnLogicExceptionsStillGetAJson500:
    """#4378's original goal, preserved: a failure in the middleware's own
    bookkeeping/header-setting logic (not call_next) still returns the
    uniform JSON 500 shape, not a bare Starlette plaintext error."""

    async def _assert_json_500(self, response):
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        assert response.media_type == "application/json"
        body = json.loads(bytes(response.body))
        assert body == {"detail": "Internal server error"}

    async def test_no_cache_middleware_header_failure(self):
        async def call_next(request):
            response = MagicMock()
            response.headers.__setitem__.side_effect = RuntimeError("boom while setting Cache-Control")
            return response

        mw = NoCacheMiddleware(app=MagicMock())
        response = await mw.dispatch(_make_request("/index.html"), call_next)

        await self._assert_json_500(response)

    async def test_security_headers_middleware_header_failure(self):
        async def call_next(request):
            response = MagicMock()
            response.headers.__setitem__.side_effect = RuntimeError("boom while setting X-Frame-Options")
            return response

        mw = SecurityHeadersMiddleware(app=MagicMock())
        response = await mw.dispatch(_make_request("/"), call_next)

        await self._assert_json_500(response)

    async def test_rate_limit_middleware_bookkeeping_failure(self):
        mw = RateLimitMiddleware(app=MagicMock())
        request = _make_request("/api/processing/foo", method="GET")

        with patch("config.middleware.time.monotonic", side_effect=RuntimeError("clock boom")):
            response = await mw.dispatch(request, _ok_call_next)

        await self._assert_json_500(response)

    async def test_origin_check_middleware_own_logic_failure(self):
        mw = OriginCheckMiddleware(app=MagicMock())
        request = _make_request("/api/processing/foo", method="POST")

        with patch("config.middleware.cors_allowed_origins", side_effect=RuntimeError("allowlist boom")):
            response = await mw.dispatch(request, _ok_call_next)

        await self._assert_json_500(response)


class TestNonRaisingDispatchStillPassesThrough:
    """A normal request must be unaffected by the try/except restructuring."""

    async def test_security_headers_middleware(self):
        mw = SecurityHeadersMiddleware(app=MagicMock())
        response = await mw.dispatch(_make_request("/index.html"), _ok_call_next)

        assert response.status_code == 200
        assert response.headers["X-Frame-Options"] == "DENY"

    async def test_rate_limit_middleware_limited_path(self):
        mw = RateLimitMiddleware(app=MagicMock())
        response = await mw.dispatch(
            _make_request("/api/processing/foo", method="GET"), _ok_call_next
        )

        assert response.status_code == 200

    async def test_origin_check_middleware_trusted_origin(self):
        mw = OriginCheckMiddleware(app=MagicMock())
        response = await mw.dispatch(
            _make_request("/api/processing/foo", method="POST"), _ok_call_next
        )

        assert response.status_code == 200
