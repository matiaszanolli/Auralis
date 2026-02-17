"""
Tests for ConnectionManager broadcast / disconnect safety (issue #2219)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

broadcast() iterates self.active_connections while disconnect() can remove
from that same list at an asyncio yield point (await send_text). Without a
snapshot the loop raises RuntimeError: list changed size during iteration.

All tests exercise the real ConnectionManager imported from config.globals.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add backend directory to path so we can import the module directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.globals import ConnectionManager


def _make_ws(send_raises: Exception | None = None) -> MagicMock:
    """Return a mock WebSocket.

    If *send_raises* is given, send_text() will raise that exception,
    simulating a stale / closed connection.
    """
    ws = MagicMock()
    if send_raises is not None:
        ws.send_text = AsyncMock(side_effect=send_raises)
    else:
        ws.send_text = AsyncMock()
    return ws


class TestBroadcastDisconnectSafety:
    """Verify that concurrent disconnect during broadcast doesn't crash."""

    @pytest.mark.asyncio
    async def test_broadcast_while_disconnect_does_not_raise(self):
        """Calling disconnect() during a broadcast must not raise RuntimeError.

        The fix snapshots active_connections with list() before iteration so
        that a concurrent removal cannot change the iterated sequence.
        """
        manager = ConnectionManager()

        # Two connected clients
        ws1 = _make_ws()
        ws2 = _make_ws()
        manager.active_connections = [ws1, ws2]

        # Make ws1.send_text disconnect ws2 mid-broadcast
        async def disconnect_ws2(*_args, **_kwargs):
            manager.disconnect(ws2)

        ws1.send_text = AsyncMock(side_effect=disconnect_ws2)

        # Should not raise RuntimeError
        await manager.broadcast({"type": "test", "data": "hello"})

        # ws2 was removed by the side effect; ws1 was not
        assert ws2 not in manager.active_connections
        assert ws1 in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_removes_stale_connections(self):
        """Connections that raise on send_text are removed after broadcast."""
        manager = ConnectionManager()

        good_ws = _make_ws()
        bad_ws = _make_ws(send_raises=RuntimeError("connection closed"))
        manager.active_connections = [good_ws, bad_ws]

        await manager.broadcast({"type": "ping"})

        assert good_ws in manager.active_connections
        assert bad_ws not in manager.active_connections
        good_ws.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_healthy_connections(self):
        """All alive connections receive the broadcast message."""
        manager = ConnectionManager()

        connections = [_make_ws() for _ in range(5)]
        manager.active_connections = list(connections)

        message = {"event": "scan_complete", "total": 100}
        await manager.broadcast(message)

        import json
        expected_json = json.dumps(message)
        for ws in connections:
            ws.send_text.assert_awaited_once_with(expected_json)

    @pytest.mark.asyncio
    async def test_broadcast_empty_connections_is_noop(self):
        """Broadcast with no clients completes without error."""
        manager = ConnectionManager()
        # Should not raise
        await manager.broadcast({"type": "noop"})

    @pytest.mark.asyncio
    async def test_disconnect_during_broadcast_of_multiple_removes_correct_one(self):
        """Only the disconnected client is removed; others remain intact."""
        manager = ConnectionManager()

        ws_keep = _make_ws()
        ws_drop = _make_ws()
        manager.active_connections = [ws_keep, ws_drop]

        call_count = 0

        async def drop_on_second(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First send: remove ws_drop so second iteration would crash
                # without the snapshot fix
                manager.disconnect(ws_drop)

        ws_keep.send_text = AsyncMock(side_effect=drop_on_second)

        await manager.broadcast({"type": "event"})

        assert ws_keep in manager.active_connections
        assert ws_drop not in manager.active_connections
