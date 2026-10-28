"""The WebSocket per-IP rate-limit buckets are swept once idle (#6171).

ip_message_log keys survive a connection on purpose (#3811) but were never deleted, so every
distinct client address (every spoofed one, before #6168) left a permanent entry.
"""

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from websocket.websocket_security import IP_LOG_SWEEP_INTERVAL, WebSocketRateLimiter  # noqa: E402


def _socket(ip: str):
    return SimpleNamespace(client=SimpleNamespace(host=ip))


def test_idle_ip_buckets_are_dropped_after_their_window():
    limiter = WebSocketRateLimiter()
    long_ago = time.time() - limiter.window_seconds - 5
    for n in range(50):
        limiter.ip_message_log[f"10.0.0.{n}"] = [long_ago]

    for _ in range(IP_LOG_SWEEP_INTERVAL):
        limiter.check_rate_limit(_socket("127.0.0.1"))

    assert set(limiter.ip_message_log) == {"127.0.0.1"}


def test_an_ip_with_a_recent_message_survives_the_sweep():
    limiter = WebSocketRateLimiter()
    limiter.ip_message_log["192.0.2.7"] = [time.time()]

    for _ in range(IP_LOG_SWEEP_INTERVAL):
        limiter.check_rate_limit(_socket("127.0.0.1"))

    assert "192.0.2.7" in limiter.ip_message_log


def test_a_reconnecting_ip_keeps_its_bucket_across_cleanup():
    limiter = WebSocketRateLimiter(max_messages_per_second=1000, max_messages_per_second_per_ip=3)
    ws = _socket("198.51.100.4")
    assert all(limiter.check_rate_limit(ws)[0] for _ in range(3))

    limiter.cleanup(ws)

    allowed, message = limiter.check_rate_limit(_socket("198.51.100.4"))
    assert allowed is False
    assert "from this client" in str(message)
