"""
Rate Limit Middleware

Per-client, per-path-prefix sliding-window limits for expensive REST
endpoints (#2575). Split out of config/middleware.py (#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, cast

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..limits import (
    RATE_LIMIT_EVICTION_INTERVAL,
    RATE_LIMIT_MAX_WINDOW_ENTRIES,
    RATE_LIMIT_PROCESSING_MAX,
    RATE_LIMIT_PROCESSING_WINDOW,
    RATE_LIMIT_SCAN_MAX,
    RATE_LIMIT_SCAN_WINDOW,
    RATE_LIMIT_SIMILARITY_MAX,
    RATE_LIMIT_SIMILARITY_WINDOW,
    RATE_LIMIT_UPLOAD_MAX,
    RATE_LIMIT_UPLOAD_WINDOW,
)
from .error_response import _middleware_error_response

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple per-path rate limiting for expensive REST endpoints (#2575).

    Uses a sliding-window counter per client IP + path prefix.
    Only applies to paths in ``_RATE_LIMITS``; all other routes pass through.
    """

    # path-prefix → (max_requests, window_seconds). Values sourced from
    # config/limits.py (#3902), each overridable via env var (#3901) —
    # see that module for the per-limit docstrings and env-var names.
    _RATE_LIMITS: dict[str, tuple[int, int]] = {
        "/api/files/upload": (RATE_LIMIT_UPLOAD_MAX, RATE_LIMIT_UPLOAD_WINDOW),
        "/api/processing": (RATE_LIMIT_PROCESSING_MAX, RATE_LIMIT_PROCESSING_WINDOW),
        "/api/library/scan": (RATE_LIMIT_SCAN_MAX, RATE_LIMIT_SCAN_WINDOW),
        "/api/similarity": (RATE_LIMIT_SIMILARITY_MAX, RATE_LIMIT_SIMILARITY_WINDOW),
    }

    # Evict stale keys every N rate-limited requests, and the hard cap on live
    # entries independent of that sweep — see config/limits.py's
    # RATE_LIMIT_EVICTION_INTERVAL / RATE_LIMIT_MAX_WINDOW_ENTRIES docstrings
    # (#2630, #4804, #3902) for the full growth-bound rationale kept there
    # rather than duplicated here.
    _EVICTION_INTERVAL = RATE_LIMIT_EVICTION_INTERVAL
    _MAX_WINDOW_ENTRIES = RATE_LIMIT_MAX_WINDOW_ENTRIES

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        # {client_key: [timestamp, ...]} — OrderedDict (not plain dict) so
        # move_to_end() can track recency for the hard-cap LRU eviction below.
        self._windows: OrderedDict[str, list[float]] = OrderedDict()
        self._request_count = 0
        # Serialize the get → prune → check → write critical section so the
        # rate limit is exact even if a future refactor introduces an await
        # inside the block (#3329). Single-threaded asyncio makes the lock
        # nearly free under normal conditions.
        self._lock: asyncio.Lock = asyncio.Lock()
        # {client_key: (last_warning_at, rejections_since_that_warning)} for
        # _log_rejection (#5375). Keys are a subset of _windows' and are
        # dropped with them in _evict_stale_keys.
        self._rejection_log: dict[str, tuple[float, int]] = {}

    def _log_rejection(
        self, key: str, client_ip: str, rule: str, window_sec: int, retry_after: int, now: float
    ) -> None:
        """WARN about a 429, at most once per client and rule per window (#5375).

        Every other rejection path in the backend logs one, and without it a
        lockout left nothing in the persisted log to explain the failures. A
        client held at the limit is rejected on every request, so logging each
        one would turn the rate limiter into a log flood. Suppressed
        rejections are counted and reported on the next warning instead.
        """
        last = self._rejection_log.get(key)
        if last is not None and now - last[0] < window_sec:
            self._rejection_log[key] = (last[0], last[1] + 1)
            return
        self._rejection_log[key] = (now, 0)
        suppressed = f" ({last[1]} more rejection(s) since the last warning)" if last and last[1] else ""
        logger.warning(
            f"Rate limit exceeded for {client_ip} on {rule}; retry after {retry_after}s{suppressed}"
        )

    def _evict_stale_keys(self, now: float) -> None:
        """Remove dict entries whose timestamps have all expired, then
        enforce the hard cap (#4804) — see _MAX_WINDOW_ENTRIES and the
        _EVICTION_INTERVAL comment above for why both are needed."""
        # Find the longest window across all rules for a conservative cutoff
        max_window = max(w for _, w in self._RATE_LIMITS.values())
        stale_keys = [
            k for k, ts in self._windows.items()
            if not ts or now - ts[-1] >= max_window
        ]
        for k in stale_keys:
            del self._windows[k]

        # Hard cap: bounds within-window growth the staleness sweep above
        # cannot catch. popitem(last=False) drops the oldest (least-recently-
        # touched) entry — dispatch() calls move_to_end() on every hit, so
        # this is true LRU, not merely insertion order.
        while len(self._windows) > self._MAX_WINDOW_ENTRIES:
            self._windows.popitem(last=False)

        # A throttle entry outlives nothing it throttles (#5375).
        for k in [k for k in self._rejection_log if k not in self._windows]:
            del self._rejection_log[k]

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # The try below covers ONLY this middleware's own rate-limit
        # bookkeeping — matching a rule, the sliding-window lock/dict
        # manipulation, and the 429 it may return. call_next(request) is
        # called exactly once, OUTSIDE the try, at the bottom of this method
        # (#4808): BaseHTTPMiddleware.call_next re-raises a downstream route
        # handler's exception at its call site, so wrapping it here caught
        # every unhandled route exception and misattributed it as
        # "Unhandled exception in RateLimitMiddleware" instead of letting it
        # reach config/app.py's registered `@app.exception_handler(Exception)`.
        # This used to be two call sites (an early-return fast path plus the
        # final one); collapsing to one after the bookkeeping block achieves
        # the same fast-path behavior (nothing below runs when no rule
        # matches) without needing call_next inside the guarded section.
        try:
            path = request.url.path

            # Find matching rate-limit rule
            limit_rule: tuple[int, int] | None = None
            matched_prefix: str | None = None
            for prefix, rule in self._RATE_LIMITS.items():
                if path.startswith(prefix):
                    limit_rule = rule
                    matched_prefix = prefix
                    break

            if limit_rule is not None and matched_prefix is not None:
                max_requests, window_sec = limit_rule
                client_ip = request.client.host if request.client else "unknown"
                # Key on the matched prefix, not the full path (#4728). Every
                # rate-limited prefix except two fixed paths fans out over a path
                # parameter (track_id, job_id, ...) — keying on the full path gave
                # each distinct resource its own fresh, effectively-unlimited
                # budget instead of the shared one the docstring promises.
                key = f"{client_ip}:{matched_prefix}"
                now = time.monotonic()

                # Critical section (#3329): eviction + sliding-window get/check/write
                # must be atomic with respect to other concurrent dispatches.
                async with self._lock:
                    # Periodic eviction of stale keys to prevent unbounded growth (#2630)
                    self._request_count += 1
                    if self._request_count >= self._EVICTION_INTERVAL:
                        self._request_count = 0
                        self._evict_stale_keys(now)

                    # Prune expired entries and check limit
                    timestamps = self._windows.get(key, [])
                    timestamps = [t for t in timestamps if now - t < window_sec]

                    if not timestamps:
                        self._windows.pop(key, None)

                    if len(timestamps) >= max_requests:
                        self._windows[key] = timestamps
                        # Recency touch for the hard-cap LRU eviction (#4804) —
                        # a client still being rate-limited is by definition
                        # active and must not be evicted ahead of quiet keys.
                        self._windows.move_to_end(key)
                        retry_after = int(window_sec - (now - timestamps[0])) + 1
                        self._log_rejection(
                            key, client_ip, matched_prefix, window_sec, retry_after, now
                        )
                        return JSONResponse(
                            status_code=429,
                            content={
                                "detail": "Too many requests",
                                # Which rule fired and how long to back off, in
                                # the JSON body so the frontend doesn't have to
                                # infer the rule from the request path or parse
                                # the Retry-After header to show a specific
                                # message (#3904) — e.g. "you're scanning too
                                # often, wait 23s" instead of a generic notice.
                                "rule": matched_prefix,
                                "retry_after_seconds": retry_after,
                            },
                            headers={"Retry-After": str(retry_after)},
                        )

                    timestamps.append(now)
                    self._windows[key] = timestamps
                    self._windows.move_to_end(key)  # recency touch (#4804)
        except Exception as exc:
            return _middleware_error_response(exc, "RateLimitMiddleware")

        return cast(Response, await call_next(request))
