"""
A rejected WebSocket handshake stops the connection lifecycle (#4703).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ConnectionManager.connect`` performs the sole Origin/loopback check and, on
rejection, called ``websocket.close(1008)`` and **returned** without calling
``accept()``. ``setup_connection`` ignored that return value: it assigned a
connection id, spawned a heartbeat task, attempted two initial pushes, and
returned normally — so the endpoint ran a full connection lifecycle on a socket
that was never established, ending in a teardown pass.

Not an auth bypass: the handshake is denied before ``accept()``, so no client
message can ever be exchanged. The cost was wasted work plus the latent hazard
that the single authoritative origin check had no way to stop the handler.

``connect`` now raises ``WebSocketOriginRejected``, which cannot be silently
dropped the way the ignored return value was.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.globals import ConnectionManager, WebSocketOriginRejected  # noqa: E402
from ws_handlers import connection as ws_connection  # noqa: E402


def _ws(origin: str | None, host: str = "127.0.0.1"):
    ws = MagicMock()
    ws.headers = {"origin": origin} if origin is not None else {}
    ws.client = MagicMock(host=host, port=54321)
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestConnectRaisesOnRejection:
    @pytest.mark.asyncio
    async def test_untrusted_origin_raises(self):
        manager = ConnectionManager()
        ws = _ws("http://evil.example.com")
        with pytest.raises(WebSocketOriginRejected):
            await manager.connect(ws)

    @pytest.mark.asyncio
    async def test_empty_origin_from_non_loopback_raises(self):
        """SIBLING: both rejection branches must signal identically."""
        manager = ConnectionManager()
        ws = _ws(None, host="10.0.0.5")
        with pytest.raises(WebSocketOriginRejected):
            await manager.connect(ws)

    @pytest.mark.asyncio
    async def test_rejection_closes_with_1008_and_never_accepts(self):
        manager = ConnectionManager()
        ws = _ws("http://evil.example.com")
        with pytest.raises(WebSocketOriginRejected):
            await manager.connect(ws)
        ws.close.assert_awaited_once_with(code=1008)
        ws.accept.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejected_socket_is_not_registered(self):
        manager = ConnectionManager()
        ws = _ws("http://evil.example.com")
        with pytest.raises(WebSocketOriginRejected):
            await manager.connect(ws)
        assert ws not in manager.active_connections
        assert manager.active_connections == []


class TestAcceptedHandshakeUnchanged:
    @pytest.mark.asyncio
    async def test_empty_origin_from_loopback_is_accepted(self):
        manager = ConnectionManager()
        ws = _ws(None, host="127.0.0.1")
        await manager.connect(ws)
        ws.accept.assert_awaited_once()
        ws.close.assert_not_awaited()
        assert ws in manager.active_connections


class TestSetupConnectionPropagates:
    """The core of the fix: the rejection must stop setup_connection."""

    @pytest.mark.asyncio
    async def test_no_heartbeat_task_is_spawned(self, monkeypatch):
        spawned = []

        def fake_spawn(coro, name=None):
            spawned.append(name)
            coro.close()  # don't leave an un-awaited coroutine behind
            return MagicMock()

        monkeypatch.setattr(ws_connection, "spawn_background_task", fake_spawn)

        manager = ConnectionManager()
        ws = _ws("http://evil.example.com")

        with pytest.raises(WebSocketOriginRejected):
            await ws_connection.setup_connection(ws, manager, None, None)

        assert spawned == [], (
            f"a rejected handshake spawned {spawned} — it sleeps up to 30 s "
            "before its first send fails"
        )

    @pytest.mark.asyncio
    async def test_no_initial_sync_frames_are_pushed(self):
        manager = ConnectionManager()
        ws = _ws("http://evil.example.com")
        settings_called = MagicMock(return_value={"enabled": True})

        with pytest.raises(WebSocketOriginRejected):
            await ws_connection.setup_connection(ws, manager, settings_called, None)

        settings_called.assert_not_called()
        ws.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_accepted_handshake_still_completes_setup(self, monkeypatch):
        """Regression guard: the happy path must be untouched."""
        monkeypatch.setattr(
            ws_connection, "spawn_background_task",
            lambda coro, name=None: (coro.close(), MagicMock())[1],
        )
        manager = ConnectionManager()
        ws = _ws(None, host="127.0.0.1")

        connection_id, heartbeat, heartbeat_task = await ws_connection.setup_connection(
            ws, manager, lambda: {"enabled": True, "preset": "adaptive", "intensity": 1.0}, None
        )

        assert connection_id
        assert heartbeat is not None
        assert heartbeat_task is not None
        ws.accept.assert_awaited_once()
        ws.send_text.assert_awaited()  # the enhancement-settings sync frame


class TestEndpointHandlesItDistinctly:
    """WIRING: the endpoint must catch it before the generic handler, so a
    policy rejection is not logged as an unexpected error with a stack trace."""

    def test_endpoint_catches_the_rejection_explicitly(self):
        import ast

        path = (
            Path(__file__).parent.parent.parent
            / "auralis-web" / "backend" / "routers" / "system.py"
        )
        source = path.read_text()
        tree = ast.parse(source)

        handlers_by_func = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Try) and inner.handlers:
                    names = []
                    for h in inner.handlers:
                        if isinstance(h.type, ast.Name):
                            names.append(h.type.id)
                        elif h.type is None:
                            names.append("bare")
                    if "WebSocketOriginRejected" in names:
                        handlers_by_func[node.name] = names

        assert handlers_by_func, (
            "no handler catches WebSocketOriginRejected — a rejected handshake "
            "would fall through to `except Exception` and be logged as an "
            "unexpected error"
        )
        for func, names in handlers_by_func.items():
            idx = names.index("WebSocketOriginRejected")
            for generic in ("Exception", "RuntimeError"):
                if generic in names:
                    assert idx < names.index(generic), (
                        f"{func}: WebSocketOriginRejected is caught after "
                        f"{generic}, so it can never be reached"
                    )
