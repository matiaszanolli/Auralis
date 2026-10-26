"""
A rejected WebSocket origin reaches the browser as close code 1008 (#5883)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ConnectionManager.connect`` closed with 1008 *before* ``accept()``. Per ASGI a
close before accept is answered as an HTTP 403 handshake failure, which a
browser reports as 1006 -- so the frontend's permanent-policy-failure path
(#5469, 1008 only) never fired and a mis-originated client retried for minutes.
Starlette's ``TestClient`` reports the app-chosen code either way and so masks
the difference; this test drives the raw ASGI messages instead.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, WebSocket

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.globals import ConnectionManager, WebSocketOriginRejected  # noqa: E402


def _app(manager: ConnectionManager) -> FastAPI:
    app = FastAPI()

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        try:
            await manager.connect(websocket)
        except WebSocketOriginRejected:
            return

    return app


async def _handshake(app: FastAPI, headers: list[tuple[bytes, bytes]], client: tuple[str, int]):
    """Run one websocket handshake; return the ASGI messages the app sent."""
    sent: list[dict] = []
    incoming = [{"type": "websocket.connect"}]

    async def receive():
        return incoming.pop(0) if incoming else {"type": "websocket.disconnect", "code": 1005}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "websocket", "path": "/ws", "raw_path": b"/ws", "query_string": b"",
        "headers": headers, "client": client, "server": ("127.0.0.1", 8765),
        "scheme": "ws", "subprotocols": [], "asgi": {"version": "3.0"},
    }
    await app(scope, receive, send)
    return sent


@pytest.mark.asyncio
async def test_untrusted_origin_is_accepted_then_closed_with_1008():
    manager = ConnectionManager()

    sent = await _handshake(
        _app(manager), [(b"origin", b"http://evil.example.com")], ("127.0.0.1", 50000)
    )

    assert [m["type"] for m in sent] == ["websocket.accept", "websocket.close"]
    assert sent[1]["code"] == 1008
    assert manager.active_connections == []


@pytest.mark.asyncio
async def test_empty_origin_from_non_loopback_is_accepted_then_closed_with_1008():
    manager = ConnectionManager()

    sent = await _handshake(_app(manager), [], ("10.0.0.5", 50000))

    assert [m["type"] for m in sent] == ["websocket.accept", "websocket.close"]
    assert sent[1]["code"] == 1008
    assert manager.active_connections == []


@pytest.mark.asyncio
async def test_trusted_origin_is_accepted_and_registered():
    manager = ConnectionManager()

    sent = await _handshake(
        _app(manager), [(b"origin", b"http://localhost:8765")], ("127.0.0.1", 50000)
    )

    assert sent[0]["type"] == "websocket.accept"
    assert all(m["type"] != "websocket.close" or m.get("code") != 1008 for m in sent)
