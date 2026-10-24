"""Regression tests for WS send-failure log classification (#5273).

send_error and send_fingerprint_progress used to catch send failures
themselves and log every one at ERROR — including a benign client
disconnect racing the send. Both now route through
controller._safe_send (stream_protocol.safe_send), which classifies by
connection state: debug when the peer is gone, warning for a genuine
failure. Neither may ever log at ERROR for a disconnect.
"""

import logging
import sys
from pathlib import Path

import pytest
from starlette.websockets import WebSocketState

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.stream_notifications import send_error, send_fingerprint_progress  # noqa: E402


class _FakeController:
    """Just the two members stream_messages uses; _safe_send delegates to the
    real stream_protocol.safe_send so the classification under test is the
    production one."""

    def _is_websocket_connected(self, websocket) -> bool:
        from core.stream_protocol import is_websocket_connected
        return is_websocket_connected(websocket)

    async def _safe_send(self, websocket, message) -> bool:
        from core.stream_protocol import safe_send
        return await safe_send(self, websocket, message)


class _DisconnectingWebsocket:
    """send_text raises the way a send-after-close does; the close lands
    during the send itself, so every connection check before it reads
    CONNECTED and every check after it reads DISCONNECTED."""

    def __init__(self) -> None:
        self._closed = False

    @property
    def client_state(self) -> WebSocketState:
        return WebSocketState.DISCONNECTED if self._closed else WebSocketState.CONNECTED

    async def send_text(self, data: str) -> None:
        self._closed = True
        raise RuntimeError('Unexpected ASGI message "websocket.send", after sending "websocket.close"')


class _BrokenWebsocket:
    """send_text raises while the connection state stays CONNECTED — a
    genuine unexpected failure, not a disconnect."""

    client_state = WebSocketState.CONNECTED

    async def send_text(self, data: str) -> None:
        raise RuntimeError("transport gone")


@pytest.mark.asyncio
async def test_send_error_on_client_disconnect_logs_at_debug_not_error(caplog):
    controller = _FakeController()
    with caplog.at_level(logging.DEBUG):
        await send_error(controller, _DisconnectingWebsocket(), track_id=1, error_message="boom")
    assert not any(r.levelno == logging.ERROR for r in caplog.records)
    assert any(r.levelno == logging.DEBUG for r in caplog.records)


@pytest.mark.asyncio
async def test_send_error_on_genuine_failure_logs_at_warning_not_error(caplog):
    controller = _FakeController()
    with caplog.at_level(logging.DEBUG):
        await send_error(controller, _BrokenWebsocket(), track_id=1, error_message="boom")
    assert not any(r.levelno == logging.ERROR for r in caplog.records)
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.asyncio
async def test_fingerprint_progress_on_disconnect_logs_at_debug_not_error(caplog):
    controller = _FakeController()
    with caplog.at_level(logging.DEBUG):
        await send_fingerprint_progress(
            controller, _DisconnectingWebsocket(), track_id=1, status="analyzing", message="…"
        )
    assert not any(r.levelno == logging.ERROR for r in caplog.records)
    assert not any("Sent fingerprint_progress" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_fingerprint_progress_success_still_logs_debug(caplog):
    class _OkWebsocket:
        client_state = WebSocketState.CONNECTED

        async def send_text(self, data: str) -> None:
            del data

    controller = _FakeController()
    with caplog.at_level(logging.DEBUG):
        await send_fingerprint_progress(
            controller, _OkWebsocket(), track_id=1, status="complete", message="done"
        )
    assert any("Sent fingerprint_progress" in r.message for r in caplog.records)
