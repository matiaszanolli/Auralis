"""
Stock Starlette middleware that answers a bad Host header or CORS preflight with a
bare 400 and logs nothing, so a DNS-rebinding probe left no evidence (#6186).
These subclasses add the one WARNING and change nothing else; OriginCheckMiddleware
already logs its 403s.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any

from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class LoggingTrustedHostMiddleware(TrustedHostMiddleware):
    """TrustedHostMiddleware that records the Host header it is about to reject."""

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if not self.allow_any and scope["type"] in ("http", "websocket"):
            host = Headers(scope=scope).get("host", "").split(":")[0]
            allowed = any(
                host == pattern or (pattern.startswith("*") and host.endswith(pattern[1:]))
                for pattern in self.allowed_hosts
            )
            if not allowed:
                logger.warning("Untrusted Host header refused: %r", host)
        await super().__call__(scope, receive, send)


class LoggingCORSMiddleware(CORSMiddleware):
    """CORSMiddleware that records a refused preflight with its Origin."""

    def preflight_response(self, request_headers: Headers) -> Response:
        response = super().preflight_response(request_headers)
        if response.status_code == 400:
            logger.warning(
                "CORS preflight refused for origin %r: %s",
                request_headers.get("origin"), bytes(response.body).decode(),
            )
        return response
