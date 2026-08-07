"""
Regression: RateLimitMiddleware._windows bounded within a single window (#4804)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

_evict_stale_keys only removed keys whose newest timestamp was already
>= max_window (60s) old. Keys created inside the CURRENT window were never
evicted regardless of how often eviction fired, so the number of live dict
entries scaled with the number of distinct client_ip:path keys seen within
a window (e.g. every track ID touched within 60s), not with the number of
clients — contradicting the #2630 comment's claim that eviction "bounds
memory". Fixed with a hard cap + LRU eviction (via OrderedDict.move_to_end
on every touch), independent of the between-window staleness sweep.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import Mock

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from config.middleware import RateLimitMiddleware


def _bare_middleware() -> RateLimitMiddleware:
    """A RateLimitMiddleware instance with no real ASGI app underneath —
    enough to unit-test _windows/_evict_stale_keys directly without going
    through thousands of real HTTP round trips."""
    return RateLimitMiddleware(app=Mock())


class TestHardCapBoundsWithinWindowGrowth:
    """The core regression: many distinct keys inside a single window must
    not grow _windows without bound."""

    def test_burst_of_distinct_fresh_keys_is_capped(self):
        mw = _bare_middleware()
        now = time.monotonic()

        # Simulate >1000 distinct client_ip:path keys, all with a FRESH
        # (current-window) timestamp — the exact case the staleness sweep
        # alone cannot catch, since none of these are >= max_window old.
        for i in range(1000):
            mw._windows[f"127.0.0.1:/api/similarity/tracks/{i}/similar"] = [now]

        assert len(mw._windows) == 1000  # sanity: nothing capped yet

        mw._evict_stale_keys(now)

        assert len(mw._windows) <= mw._MAX_WINDOW_ENTRIES

    def test_cap_holds_for_a_burst_larger_than_the_cap(self):
        mw = _bare_middleware()
        mw._MAX_WINDOW_ENTRIES = 500  # shrink for a fast test
        now = time.monotonic()

        for i in range(2000):
            mw._windows[f"127.0.0.1:/api/similarity/tracks/{i}/similar"] = [now]

        mw._evict_stale_keys(now)

        assert len(mw._windows) <= 500

    def test_stale_entries_still_evicted_as_before(self):
        """Regression guard: the pre-existing #2630 between-window sweep
        must not be broken by the hard-cap addition."""
        mw = _bare_middleware()
        now = time.monotonic()
        max_window = max(w for _, w in mw._RATE_LIMITS.values())

        mw._windows["127.0.0.1:/api/processing"] = [now - max_window - 1]  # stale
        mw._windows["127.0.0.1:/api/similarity"] = [now]  # fresh

        mw._evict_stale_keys(now)

        assert "127.0.0.1:/api/processing" not in mw._windows
        assert "127.0.0.1:/api/similarity" in mw._windows


class TestEvictionIsLRUNotArbitrary:
    """Active clients must never be evicted ahead of quiet ones."""

    def test_recently_touched_key_survives_over_untouched_older_ones(self):
        mw = _bare_middleware()
        mw._MAX_WINDOW_ENTRIES = 3
        now = time.monotonic()

        # Insertion order: a, b, c, d — all fresh, cap is 3.
        for k in ("a", "b", "c", "d"):
            mw._windows[k] = [now]

        # Touch "a" so it's the most-recently-used, despite being oldest by
        # insertion order — a real client making a second request.
        mw._windows.move_to_end("a")

        mw._evict_stale_keys(now)

        assert len(mw._windows) == 3
        assert "a" in mw._windows, "a recently-touched entry must survive eviction"
        # "b" was the least-recently-touched of the four (never moved), so
        # it must be the one dropped to get from 4 down to the cap of 3.
        assert "b" not in mw._windows


class TestRateLimitingStillWorksNormally:
    """The fix must not change legitimate rate-limiting behavior."""

    @pytest.mark.asyncio
    async def test_normal_client_still_gets_rate_limited(self):
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.get("/api/similarity")
        async def handler():
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            responses = await asyncio.gather(*[client.get("/api/similarity") for _ in range(25)])

        ok = sum(1 for r in responses if r.status_code == 200)
        limited = sum(1 for r in responses if r.status_code == 429)
        assert ok == 20  # /api/similarity is configured 20/60s
        assert limited == 5

    @pytest.mark.asyncio
    async def test_many_distinct_paths_stay_capped_through_real_dispatch(self):
        """End-to-end: drive enough distinct paths through the real
        dispatch() (not just direct _windows manipulation) to trigger both
        the periodic eviction and the hard cap, with both shrunk so the test
        stays fast."""
        app = FastAPI()

        @app.get("/api/similarity/{track_id}")
        async def handler(track_id: int):
            return {"ok": True}

        app.add_middleware(RateLimitMiddleware)
        # Force the lazily-built middleware stack into existence now, so the
        # live RateLimitMiddleware instance can be found and its thresholds
        # shrunk BEFORE any request is dispatched — Starlette builds (and
        # caches) app.middleware_stack on first use otherwise.
        app.middleware_stack = app.build_middleware_stack()
        instance = app.middleware_stack
        while instance is not None and not isinstance(instance, RateLimitMiddleware):
            instance = getattr(instance, "app", None)
        assert isinstance(instance, RateLimitMiddleware)
        instance._MAX_WINDOW_ENTRIES = 50
        instance._EVICTION_INTERVAL = 10

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 300 distinct track IDs -> 300 distinct keys, well past the
            # shrunk cap and eviction interval, so both fire repeatedly
            # during this loop, not just once at the end.
            for i in range(300):
                await client.get(f"/api/similarity/{i}")

        # Eviction runs at the top of dispatch(), before the CURRENT
        # request's own key is inserted — so size can be cap+1 right after
        # the eviction that just ran, settling back to <= cap on the next
        # pass. The real invariant under test is "stays near the cap
        # indefinitely", not "never exceeds it by a single in-flight entry".
        assert len(instance._windows) <= 51, (
            f"grew to {len(instance._windows)} despite a cap of 50 — "
            "within-window growth is not bounded"
        )
