"""
The WebSocket connection count is capped (#6171)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

active_connections grew without bound, and every broadcast fans out to all of it. The next connection
beyond WS_MAX_CONNECTIONS is accepted just long enough to close it with 1013 (try again later); the
established ones are untouched and a freed slot is reusable.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config import globals as g
from config.limits import WS_MAX_CONNECTIONS


def _socket():
    ws = MagicMock()
    ws.headers = {"origin": ""}
    ws.client = MagicMock(host="127.0.0.1", port=1234)
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def manager():
    return g.ConnectionManager()


async def test_connections_up_to_the_cap_register(manager):
    sockets = [_socket() for _ in range(WS_MAX_CONNECTIONS)]
    for ws in sockets:
        await manager.connect(ws)

    assert manager.active_connections == sockets
    assert all(ws.close.await_count == 0 for ws in sockets)


async def test_the_next_one_is_closed_with_1013_and_not_registered(manager):
    for _ in range(WS_MAX_CONNECTIONS):
        await manager.connect(_socket())
    extra = _socket()

    with pytest.raises(g.WebSocketOriginRejected, match="connection limit"):
        await manager.connect(extra)

    extra.close.assert_awaited_once_with(code=1013)
    assert extra not in manager.active_connections
    assert len(manager.active_connections) == WS_MAX_CONNECTIONS


async def test_a_freed_slot_can_be_reused(manager):
    sockets = [_socket() for _ in range(WS_MAX_CONNECTIONS)]
    for ws in sockets:
        await manager.connect(ws)
    await manager.disconnect(sockets[0])

    late = _socket()
    await manager.connect(late)

    assert late in manager.active_connections and len(manager.active_connections) == WS_MAX_CONNECTIONS


async def test_simultaneous_handshakes_cannot_exceed_the_cap(manager):
    results = await asyncio.gather(
        *[manager.connect(_socket()) for _ in range(WS_MAX_CONNECTIONS + 8)], return_exceptions=True
    )

    assert len(manager.active_connections) == WS_MAX_CONNECTIONS
    assert sum(isinstance(r, g.WebSocketOriginRejected) for r in results) == 8


async def test_an_origin_rejection_still_closes_with_1008(manager):
    ws = _socket()
    ws.headers = {"origin": "http://evil.example"}

    with pytest.raises(g.WebSocketOriginRejected):
        await manager.connect(ws)

    ws.close.assert_awaited_once_with(code=1008)
