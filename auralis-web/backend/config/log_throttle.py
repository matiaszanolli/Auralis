"""One WARNING per reason per window for rejections a remote page can trigger (#6188).

Any web page can fire cross-origin POSTs and any local peer can send junk WebSocket
frames, and each rejection logged a line. electron-log keeps 1 MiB and one archive,
so a flood evicted the earlier security entries within minutes. The first rejection
of a reason is logged in full; later ones inside the window are only counted and
reported on the next warning, as RateLimitMiddleware does per client (#5375).

``key`` must come from a small fixed set (a rejection reason), never from request
data, so the table stays bounded.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import threading
import time

LOG_THROTTLE_WINDOW_S = 60.0

_lock = threading.Lock()
_state: dict[str, tuple[float, int]] = {}  # key -> (last_logged_at, suppressed_since)


def warn_throttled(
    log: logging.Logger,
    key: str,
    message: str,
    *,
    window: float = LOG_THROTTLE_WINDOW_S,
    now: float | None = None,
) -> bool:
    """Log ``message`` at WARNING unless ``key`` already logged inside ``window``; True when logged."""
    now = time.monotonic() if now is None else now
    with _lock:
        last = _state.get(key)
        if last is not None and now - last[0] < window:
            _state[key] = (last[0], last[1] + 1)
            return False
        _state[key] = (now, 0)
    suppressed = f" ({last[1]} more like it in the last window)" if last and last[1] else ""
    log.warning(f"{message}{suppressed}")
    return True
