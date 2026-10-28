"""A transient ping failure does not end staleness monitoring for good (#5077).

run_heartbeat_loop returned on the first failed ping send, so one hiccup on a live socket silently
disabled eviction for the rest of the connection's life; and a RuntimeError from closing a socket
that raced to already-closed escaped the background task as an ERROR with a stack trace.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from websocket.websocket_protocol import HeartbeatManager  # noqa: E402
from ws_handlers import connection as connection_module  # noqa: E402

pytestmark = pytest.mark.asyncio


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now


async def _run(send_results, *, connected=True, close_error=None, stale=False, max_wakeups=12):
    """Drive the real loop; returns (send attempts, close calls)."""
    clock = _Clock()
    heartbeat = HeartbeatManager(interval_seconds=30, timeout_seconds=10)
    heartbeat.is_stale = lambda _connection_id: stale  # type: ignore[method-assign]
    wakeups = 0

    async def fake_sleep(delay):
        nonlocal wakeups
        wakeups += 1
        if wakeups > max_wakeups:
            raise asyncio.CancelledError
        clock.now += delay

    websocket = MagicMock()
    websocket.client_state.name = "CONNECTED" if connected else "DISCONNECTED"
    websocket.close = AsyncMock(side_effect=close_error)
    loop = MagicMock()
    loop.time = clock.time
    send = AsyncMock(side_effect=send_results)

    with (
        patch.object(connection_module.asyncio, "sleep", fake_sleep),
        patch.object(connection_module.asyncio, "get_running_loop", lambda: loop),
        patch.object(connection_module, "safe_send_text", send),
    ):
        try:
            await connection_module.run_heartbeat_loop(websocket, heartbeat, "c1")
        except asyncio.CancelledError:
            pass
    return send.await_count, websocket.close.await_count


async def test_one_failed_ping_on_a_live_socket_does_not_end_the_loop():
    # fail once, then succeed forever: the loop must reach the later pings.
    attempts, _ = await _run([False] + [True] * 20)

    assert attempts > 2


async def test_repeated_failures_on_a_live_socket_eventually_end_the_loop():
    attempts, _ = await _run([False] * 20)

    assert attempts == 3


async def test_a_dead_socket_ends_the_loop_at_the_first_failure():
    attempts, _ = await _run([False] * 20, connected=False)

    assert attempts == 1


async def test_close_racing_an_already_closed_socket_is_not_a_task_failure():
    # The connection is stale, so the loop evicts it; close() then raises.
    _, closes = await _run([True] * 20, stale=True, close_error=RuntimeError("already closed"))

    assert closes == 1
