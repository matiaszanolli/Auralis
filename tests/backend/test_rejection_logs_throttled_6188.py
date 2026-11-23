"""Attacker-triggerable rejection logs are throttled per reason (#6188), without hiding a burst (#6541).

Any web page can fire cross-origin POSTs, and electron-log keeps 1 MiB with one
archive, so one WARNING per rejection let a flood evict earlier security entries.
The throttle then hid too much: the suppressed count was written only if another
rejection came after the window, and a second hostile origin inside the window
left no trace. The count is now flushed when the window ends, and each distinct
detail (origin, host, client) is logged once per window, at most 32 of them.
"""

import logging
import sys
import threading
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
    log_throttle.reset()
    yield
    log_throttle.reset()


def test_first_logs_then_suppresses_then_reports_the_count(caplog):
    log = logging.getLogger("test.throttle")
    with caplog.at_level(logging.WARNING, logger="test.throttle"):
        assert log_throttle.warn_throttled(log, "k", "one", now=0.0)
        assert not log_throttle.warn_throttled(log, "k", "two", now=1.0)
        assert not log_throttle.warn_throttled(log, "k", "three", now=2.0)
        assert log_throttle.warn_throttled(log, "k", "four", now=61.0)
        assert log_throttle.warn_throttled(log, "other", "five", now=61.0)

    assert [r.getMessage() for r in caplog.records] == [
        "one", "2 more k rejection(s) in the last 60s window", "four", "five",
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
    # Each distinct origin once per window (#6541), bounded so a flood stays small.
    assert len(rejected) == log_throttle.MAX_DETAILS_PER_WINDOW


def test_the_suppressed_count_is_flushed_when_the_window_ends(caplog):
    log = logging.getLogger("test.throttle")
    with caplog.at_level(logging.WARNING, logger="test.throttle"):
        log_throttle.warn_throttled(log, "k", "one", now=0.0)
        for t in (1.0, 2.0, 3.0):
            log_throttle.warn_throttled(log, "k", "again", now=t)
        assert log_throttle.flush_expired(now=30.0) == 0  # window still open
        assert log_throttle.flush_expired(now=60.0) == 1
        assert log_throttle.flush_expired(now=90.0) == 0  # written once

    assert [r.getMessage() for r in caplog.records] == ["one", "3 more k rejection(s) in the last 60s window"]


def test_a_flush_timer_writes_the_count_with_no_further_rejection():
    """The timer writes from its own thread, so the test collects records with its own handler and
    is signalled only after a record is appended: reading caplog after a filter-set event raced the
    handler on that thread (CI run 45282187108)."""
    log = logging.getLogger("test.throttle.flush")
    messages: list[str] = []
    summary_written = threading.Event()

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())
            if "more k rejection" in record.getMessage():
                summary_written.set()

    handler = _Collect(logging.WARNING)
    log.addHandler(handler)
    try:
        log_throttle.warn_throttled(log, "k", "one", window=0.2)
        log_throttle.warn_throttled(log, "k", "again", window=0.2)
        assert summary_written.wait(5), "the suppressed count was never written"
    finally:
        log.removeHandler(handler)

    assert messages == ["one", "1 more k rejection(s) in the last 0.2s window"]


def test_a_new_detail_inside_the_window_is_logged_and_the_set_is_bounded(caplog):
    log = logging.getLogger("test.throttle")
    with caplog.at_level(logging.WARNING, logger="test.throttle"):
        assert log_throttle.warn_throttled(log, "origin", "benign", detail="https://a.example", now=0.0)
        assert log_throttle.warn_throttled(log, "origin", "hostile", detail="https://b.example", now=1.0)
        assert not log_throttle.warn_throttled(log, "origin", "repeat", detail="https://b.example", now=2.0)
        for i in range(100):
            log_throttle.warn_throttled(log, "origin", f"o{i}", detail=f"https://{i}.example", now=3.0)

    logged = [r.getMessage() for r in caplog.records]
    assert logged[:2] == ["benign", "hostile"]
    assert len(logged) == log_throttle.MAX_DETAILS_PER_WINDOW
