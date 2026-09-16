"""
RateLimitMiddleware logs its 429s, throttled per client and rule (#5375)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every other rejection path in the backend logs a WARNING, but the 429 branch
returned silently, so a rate-limit lockout left nothing in the persisted log.
A client held at the limit is rejected on every request, so the warning is
emitted at most once per client and rule per window, with a count of the
rejections suppressed in between.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import config.middleware.rate_limit as middleware_module  # owns `time` and the logger (#5479)
from config.limits import RATE_LIMIT_SCAN_MAX, RATE_LIMIT_SCAN_WINDOW
from config.middleware import RateLimitMiddleware


def _app() -> FastAPI:
    app = FastAPI()

    @app.post("/api/library/scan")
    async def scan():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)
    return app


async def _statuses(client: httpx.AsyncClient, count: int) -> list[int]:
    return [(await client.post("/api/library/scan")).status_code for _ in range(count)]


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == middleware_module.logger.name and record.levelno == logging.WARNING
    ]


@pytest.mark.asyncio
async def test_a_lockout_logs_once_per_window_naming_client_and_rule(monkeypatch, caplog):
    clock = SimpleNamespace(now=1000.0)
    # Replace only the middleware's `time` reference; the event loop keeps the real clock.
    monkeypatch.setattr(middleware_module, "time", SimpleNamespace(monotonic=lambda: clock.now))
    caplog.set_level(logging.WARNING, logger=middleware_module.logger.name)

    async with httpx.AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        assert (await _statuses(client, RATE_LIMIT_SCAN_MAX + 20)).count(429) == 20

        warnings = _warnings(caplog)
        assert len(warnings) == 1
        assert "127.0.0.1" in warnings[0]
        assert "/api/library/scan" in warnings[0]

        clock.now += RATE_LIMIT_SCAN_WINDOW + 1
        assert (await _statuses(client, RATE_LIMIT_SCAN_MAX + 1)).count(429) == 1

    warnings = _warnings(caplog)
    assert len(warnings) == 2
    assert "19 more rejection(s)" in warnings[1]


def test_throttle_entries_are_evicted_with_their_windows():
    middleware = RateLimitMiddleware(None)
    middleware._rejection_log["10.0.0.2:/api/similarity"] = (0.0, 5)

    middleware._evict_stale_keys(now=1_000_000.0)

    assert middleware._rejection_log == {}
