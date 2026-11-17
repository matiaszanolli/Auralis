"""Attacker-triggerable rejection logs are throttled per reason (#6188).

Any web page can fire cross-origin POSTs, and electron-log keeps 1 MiB with one
archive, so one WARNING per rejection let a flood evict earlier security entries.
"""

import logging
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config import log_throttle  # noqa: E402
from config.middleware import setup_middleware  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_throttle():
    log_throttle._state.clear()
    yield
    log_throttle._state.clear()


def test_first_logs_then_suppresses_then_reports_the_count(caplog):
    log = logging.getLogger("test.throttle")
    with caplog.at_level(logging.WARNING, logger="test.throttle"):
        assert log_throttle.warn_throttled(log, "k", "one", now=0.0)
        assert not log_throttle.warn_throttled(log, "k", "two", now=1.0)
        assert not log_throttle.warn_throttled(log, "k", "three", now=2.0)
        assert log_throttle.warn_throttled(log, "k", "four", now=61.0)
        assert log_throttle.warn_throttled(log, "other", "five", now=61.0)

    assert [r.getMessage() for r in caplog.records] == [
        "one", "four (2 more like it in the last window)", "five",
    ]


@pytest.mark.asyncio
async def test_a_cross_origin_post_flood_logs_one_warning(caplog):
    app = FastAPI()
    setup_middleware(app)

    @app.post("/api/thing")
    async def thing():
        return {"ok": True}

    with caplog.at_level(logging.WARNING):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for i in range(50):
                response = await client.post("/api/thing", headers={"Origin": f"https://evil{i}.example"})
                assert response.status_code == 403

    rejected = [r for r in caplog.records if "untrusted origin" in r.getMessage()]
    assert len(rejected) == 1
