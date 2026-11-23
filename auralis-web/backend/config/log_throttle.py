"""One WARNING per reason per window for rejections a remote page can trigger (#6188).

Any web page can fire cross-origin POSTs and any local peer can send junk WebSocket
frames, and each rejection logged a line. electron-log keeps 1 MiB and one archive,
so a flood evicted the earlier security entries within minutes. The first rejection
of a reason is logged in full; later ones inside the window are counted.

Two gaps that left a burst under-reported are closed (#6541): the count is written
when the window ends (a daemon timer), not only if another rejection arrives later;
and a rejection whose ``detail`` (the origin, host or client) has not been seen in
the window is logged too, so a second hostile origin is not hidden behind a first,
benign one. RateLimitMiddleware throttles its 429 warnings here as well (#5375).

``key`` must come from a small fixed set (a rejection reason), never from request
data, and at most ``MAX_DETAILS_PER_WINDOW`` details are remembered per key, so the
table stays bounded.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import threading
import time
from dataclasses import dataclass, field

LOG_THROTTLE_WINDOW_S = 60.0
MAX_DETAILS_PER_WINDOW = 32


@dataclass
class _Window:
    log: logging.Logger
    started: float
    length: float
    suppressed: int = 0
    details: set[str] = field(default_factory=set)


_lock = threading.Lock()
_state: dict[str, _Window] = {}
_flush_timer: threading.Timer | None = None


def warn_throttled(
    log: logging.Logger,
    key: str,
    message: str,
    *,
    detail: str | None = None,
    window: float = LOG_THROTTLE_WINDOW_S,
    now: float | None = None,
) -> bool:
    """Log ``message`` at WARNING unless ``key`` already logged it inside ``window``; True when logged.

    Inside the window it is still logged when ``detail`` is new to the window (bounded). ``now``
    is for tests: a call on a supplied clock arms no flush timer, which runs on the real one.
    """
    real_clock = now is None
    now = time.monotonic() if now is None else now
    summary = None
    with _lock:
        current = _state.get(key)
        if current is not None and now - current.started < window:
            if detail is None or detail in current.details or len(current.details) >= MAX_DETAILS_PER_WINDOW:
                current.suppressed += 1
                if real_clock:
                    _arm_flush_locked(current.started + current.length - now)
                return False
            current.details.add(detail)
        else:
            if current is not None and current.suppressed:
                summary = _summary(key, current)
            _state[key] = _Window(log, now, window, details={detail} if detail is not None else set())
    if summary is not None:
        log.warning(summary)
    log.warning(message)
    return True


def flush_expired(now: float | None = None) -> int:
    """Write the suppressed count of every window that has ended; returns how many were written."""
    real_clock = now is None
    now = time.monotonic() if now is None else now
    due: list[tuple[logging.Logger, str]] = []
    with _lock:
        for key, current in _state.items():
            if current.suppressed and now - current.started >= current.length:
                due.append((current.log, _summary(key, current)))
                current.suppressed = 0
        pending = [c.started + c.length - now for c in _state.values() if c.suppressed]
        if pending and real_clock:
            _arm_flush_locked(min(pending))
    for log, summary in due:
        log.warning(summary)
    return len(due)


def _summary(key: str, window: _Window) -> str:
    return f"{window.suppressed} more {key} rejection(s) in the last {window.length:g}s window"


def _on_flush_timer() -> None:
    global _flush_timer
    with _lock:
        _flush_timer = None
    flush_expired()


def _arm_flush_locked(delay: float) -> None:
    """One daemon timer at a time, for the earliest window with a pending count. Caller holds _lock."""
    global _flush_timer
    if _flush_timer is not None:
        return
    _flush_timer = threading.Timer(max(delay, 0.0) + 0.05, _on_flush_timer)
    _flush_timer.daemon = True
    _flush_timer.start()


def reset() -> None:
    """Forget every window and cancel a pending flush (tests: the state is process-wide)."""
    global _flush_timer
    with _lock:
        _state.clear()
        timer, _flush_timer = _flush_timer, None
    if timer is not None:
        timer.cancel()
