"""
Tests for ConnectionManager broadcast / disconnect safety (issue #2219)
and origin-check security (issue #3845).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

broadcast() iterates self.active_connections while disconnect() can remove
from that same list at an asyncio yield point (await send_text). Without a
snapshot the loop raises RuntimeError: list changed size during iteration.

All tests exercise the real ConnectionManager imported from config.globals.
"""

import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add backend directory to path so we can import the module directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.globals import ConnectionManager, WebSocketOriginRejected


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
            await manager.disconnect(ws2)

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
                await manager.disconnect(ws_drop)

        ws_keep.send_text = AsyncMock(side_effect=drop_on_second)

        await manager.broadcast({"type": "event"})

        assert ws_keep in manager.active_connections
        assert ws_drop not in manager.active_connections


class TestBroadcastConcurrency:
    """Regression tests for #3867 — broadcast must not serialise on one client."""

    @pytest.mark.asyncio
    async def test_slow_client_does_not_delay_other_clients(self):
        """A slow client must not push the others' sends out behind it.

        Serial iteration made client N wait for the cumulative send time of
        clients 0..N-1. With concurrent sends the fast clients complete while
        the slow one is still blocked, so the total wall-clock is one slow
        send, not the sum.
        """
        manager = ConnectionManager()

        slow_delay = 0.2
        slow_ws = _make_ws()

        async def slow_send(*_args, **_kwargs):
            await asyncio.sleep(slow_delay)

        slow_ws.send_text = AsyncMock(side_effect=slow_send)

        fast_connections = [_make_ws() for _ in range(4)]
        # Slow client first so a serial loop would block every fast client.
        manager.active_connections = [slow_ws, *fast_connections]

        loop = asyncio.get_running_loop()
        start = loop.time()
        completion_times: list[float] = []

        for ws in fast_connections:
            ws.send_text = AsyncMock(
                side_effect=lambda *_a, **_kw: completion_times.append(loop.time())
            )

        await manager.broadcast({"type": "state"})

        assert len(completion_times) == 4
        # Every fast client was served well before the slow one finished.
        for finished_at in completion_times:
            assert finished_at - start < slow_delay / 2

        # And nobody was evicted: a slow-but-within-timeout client stays.
        assert manager.active_connections == [slow_ws, *fast_connections]

    @pytest.mark.asyncio
    async def test_broadcast_costs_one_timeout_not_n(self, monkeypatch):
        """N wedged clients cost one timeout total, not N sequential timeouts."""
        import config.globals as globals_module

        monkeypatch.setattr(globals_module, "BROADCAST_SEND_TIMEOUT", 0.1)

        async def never_completes(*_args, **_kwargs):
            await asyncio.sleep(3600)

        manager = ConnectionManager()
        wedged = [_make_ws() for _ in range(5)]
        for ws in wedged:
            ws.send_text = AsyncMock(side_effect=never_completes)
        manager.active_connections = list(wedged)

        loop = asyncio.get_running_loop()
        start = loop.time()
        await manager.broadcast({"type": "state"})
        elapsed = loop.time() - start

        # Serial would be 5 x 0.1s; concurrent is a single 0.1s window.
        assert elapsed < 0.3
        # All five exceeded the timeout and were evicted.
        assert manager.active_connections == []

    @pytest.mark.asyncio
    async def test_healthy_clients_survive_a_wedged_peer(self, monkeypatch):
        """Only the timed-out connection is evicted; healthy peers still get the frame."""
        import config.globals as globals_module

        monkeypatch.setattr(globals_module, "BROADCAST_SEND_TIMEOUT", 0.1)

        async def never_completes(*_args, **_kwargs):
            await asyncio.sleep(3600)

        manager = ConnectionManager()
        wedged_ws = _make_ws()
        wedged_ws.send_text = AsyncMock(side_effect=never_completes)
        healthy_ws = _make_ws()
        manager.active_connections = [wedged_ws, healthy_ws]

        await manager.broadcast({"type": "state"})

        assert manager.active_connections == [healthy_ws]
        healthy_ws.send_text.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests: Origin-header security (#3845)
# ---------------------------------------------------------------------------

def _make_connect_ws(origin: str, client_host: str = "127.0.0.1") -> MagicMock:
    """Return a mock WebSocket for connect() tests.

    ``origin`` is the value returned by headers.get("origin", "").
    ``client_host`` simulates websocket.client.host.
    """
    ws = MagicMock()
    ws.headers = MagicMock()
    ws.headers.get = MagicMock(side_effect=lambda key, default="": origin if key == "origin" else default)
    client = MagicMock()
    client.host = client_host
    client.port = 12345
    ws.client = client
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    return ws


class TestOriginCheck:
    """Regression tests for WebSocket origin validation (issues #2413, #3845)."""

    @pytest.mark.asyncio
    async def test_allowed_origin_accepted(self):
        """A connection whose Origin is in ALLOWED_WS_ORIGINS is accepted.

        Uses port 8765 (the backend, always allowed) rather than a dev port —
        the 3000-3006 range is now gated on is_dev_mode() (#4350) and absent in
        the non-dev test environment.
        """
        manager = ConnectionManager()
        ws = _make_connect_ws(origin="http://localhost:8765")
        await manager.connect(ws)
        ws.accept.assert_awaited_once()
        ws.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_untrusted_origin_rejected(self):
        """A connection with a non-empty, unlisted Origin is rejected (code 1008).

        #4703: rejection now RAISES rather than returning, so the caller
        cannot ignore it and run a lifecycle on an unaccepted socket.
        """
        manager = ConnectionManager()
        ws = _make_connect_ws(origin="https://evil.example.com")
        with pytest.raises(WebSocketOriginRejected):
            await manager.connect(ws)
        ws.close.assert_awaited_once_with(code=1008)
        ws.accept.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_origin_loopback_accepted(self):
        """Empty Origin from loopback (127.0.0.1) is accepted without close (#3845)."""
        manager = ConnectionManager()
        ws = _make_connect_ws(origin="", client_host="127.0.0.1")
        await manager.connect(ws)
        ws.accept.assert_awaited_once()
        ws.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_origin_ipv6_loopback_accepted(self):
        """Empty Origin from ::1 (IPv6 loopback) is also accepted (#3845)."""
        manager = ConnectionManager()
        ws = _make_connect_ws(origin="", client_host="::1")
        await manager.connect(ws)
        ws.accept.assert_awaited_once()
        ws.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_origin_non_loopback_rejected(self):
        """Empty Origin from a non-loopback host is rejected (code 1008) (#3845).

        #4703: raises, like the untrusted-origin branch — both signal identically.
        """
        manager = ConnectionManager()
        ws = _make_connect_ws(origin="", client_host="192.168.1.42")
        with pytest.raises(WebSocketOriginRejected):
            await manager.connect(ws)
        ws.close.assert_awaited_once_with(code=1008)
        ws.accept.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_origin_null_client_rejected(self):
        """Empty Origin with websocket.client=None (edge case) is rejected (#3845)."""
        manager = ConnectionManager()
        ws = _make_connect_ws(origin="", client_host="127.0.0.1")
        ws.client = None  # override to simulate missing client info
        with pytest.raises(WebSocketOriginRejected):
            await manager.connect(ws)
        ws.close.assert_awaited_once_with(code=1008)
        ws.accept.assert_not_awaited()


class TestConnectionLifecycleLogLevels:
    """#3903: routine connect/disconnect must not log at INFO -- it drowns
    out genuinely important INFO events (e.g. every wscat/test-script
    loopback connection used to log one of these). Rejections still WARN
    (already covered by TestOriginCheck); stale-connection removal in
    broadcast() is deliberately left at INFO (an anomaly, not routine
    traffic) -- not tested here since it's unchanged."""

    @pytest.mark.asyncio
    async def test_successful_connect_does_not_log_at_info(self, caplog):
        manager = ConnectionManager()
        ws = _make_connect_ws(origin="http://localhost:8765")

        with caplog.at_level(logging.DEBUG, logger="config.globals"):
            await manager.connect(ws)

        assert not [r for r in caplog.records if r.levelno >= logging.INFO], (
            "a successful connect must not log at INFO or above"
        )
        assert any(
            "WebSocket connected from" in r.message and r.levelno == logging.DEBUG
            for r in caplog.records
        ), "the connect message must still be emitted, just at DEBUG"

    @pytest.mark.asyncio
    async def test_disconnect_does_not_log_at_info(self, caplog):
        manager = ConnectionManager()
        ws = _make_connect_ws(origin="http://localhost:8765")
        await manager.connect(ws)

        with caplog.at_level(logging.DEBUG, logger="config.globals"):
            await manager.disconnect(ws)

        assert not [r for r in caplog.records if r.levelno >= logging.INFO], (
            "a routine disconnect must not log at INFO or above"
        )
        assert any(
            "WebSocket disconnected from" in r.message and r.levelno == logging.DEBUG
            for r in caplog.records
        ), "the disconnect message must still be emitted, just at DEBUG"

    @pytest.mark.asyncio
    async def test_rejected_connect_still_warns(self, caplog):
        """Sibling check: the fix must not silence the actually-important
        rejection path while quieting the routine success path."""
        manager = ConnectionManager()
        ws = _make_connect_ws(origin="https://evil.example.com")

        with caplog.at_level(logging.DEBUG, logger="config.globals"):
            with pytest.raises(WebSocketOriginRejected):
                await manager.connect(ws)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("untrusted origin" in r.message for r in warnings)
