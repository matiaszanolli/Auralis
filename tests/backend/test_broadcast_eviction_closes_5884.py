"""A client evicted by broadcast() is closed, not silently unsubscribed (#5884).

`broadcast()` drops a client whose send exceeds `BROADCAST_SEND_TIMEOUT` from
`active_connections`. Nothing re-adds it, and its receive loop, heartbeat and
stream task kept running, so one slow patch blinded that tab to every later
broadcast while it still looked connected. Eviction now closes the socket with
1013, which the frontend retries; the reconnect resyncs via setup_connection.
"""

import asyncio
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

from config.globals import ConnectionManager  # noqa: E402


class _Client:
    def __init__(self, *, stall_send: bool = False, stall_close: bool = False):
        self.stall_send = stall_send
        self.stall_close = stall_close
        self.received: list[str] = []
        self.close_codes: list[int] = []

    async def send_text(self, message: str) -> None:
        if self.stall_send:
            await asyncio.Event().wait()
        self.received.append(message)

    async def close(self, code: int = 1000) -> None:
        self.close_codes.append(code)
        if self.stall_close:
            await asyncio.Event().wait()


async def _drain_background_tasks() -> None:
    current = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks() if t is not current]
    await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), timeout=2.0)


@pytest.fixture
def fast_timeout(monkeypatch):
    monkeypatch.setattr("config.globals.BROADCAST_SEND_TIMEOUT", 0.05)


@pytest.mark.asyncio
async def test_timed_out_client_is_closed_with_1013(fast_timeout):
    mgr = ConnectionManager()
    stalled = _Client(stall_send=True)
    healthy = _Client()
    mgr.active_connections.extend([stalled, healthy])  # type: ignore[list-item]

    await mgr.broadcast({"type": "position_changed"})
    await _drain_background_tasks()

    assert stalled.close_codes == [1013]
    assert healthy.close_codes == [], "a client that received the frame was closed"
    assert mgr.active_connections == [healthy]


@pytest.mark.asyncio
async def test_a_wedged_close_does_not_delay_the_broadcast(fast_timeout):
    """The close frame is backpressured too; broadcast() must not wait on it."""
    mgr = ConnectionManager()
    stalled = _Client(stall_send=True, stall_close=True)
    mgr.active_connections.append(stalled)  # type: ignore[arg-type]

    loop = asyncio.get_running_loop()
    start = loop.time()
    await mgr.broadcast({"type": "x"})
    assert loop.time() - start < 0.5

    # The background close is itself bounded and swallows its timeout.
    await _drain_background_tasks()
    assert stalled.close_codes == [1013]


@pytest.mark.asyncio
async def test_raising_client_is_closed_too():
    mgr = ConnectionManager()
    broken = _Client()

    async def _raise(_message: str) -> None:
        raise RuntimeError("socket closed")

    broken.send_text = _raise  # type: ignore[method-assign]
    mgr.active_connections.append(broken)  # type: ignore[arg-type]

    await mgr.broadcast({"type": "x"})
    await _drain_background_tasks()

    assert broken.close_codes == [1013]
    assert mgr.active_connections == []
