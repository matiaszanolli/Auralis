"""
Invalid and binary WebSocket frames are charged to the rate limiter (#5915)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The receive loop answered binary frames and every failed
``validate_and_parse_message`` with an error frame *before* the rate limit ran,
so a client could drive unlimited request/response traffic. A rejected frame is
now charged to the limiter and, once the budget is spent, dropped without a
reply. The limiter also uses the shared ``WS_MAX_MESSAGES_PER_SECOND`` instead
of a repeated literal, and uvicorn is told to bound inbound frames at
``WS_MAX_MESSAGE_SIZE``.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from config.limits import WS_MAX_MESSAGE_SIZE, WS_MAX_MESSAGES_PER_SECOND  # noqa: E402
from routers import system  # noqa: E402
from websocket.websocket_security import (  # noqa: E402
    WebSocketRateLimiter,
    receive_text_frame,
    validate_and_parse_message,
)


def _ws():
    ws = MagicMock()
    ws.client = MagicMock(host="127.0.0.1", port=50000)
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive = AsyncMock(return_value={"type": "websocket.receive", "bytes": b"\x00"})
    return ws


def _replies(ws) -> int:
    return ws.send_text.await_count + ws.send_json.await_count


@pytest.mark.asyncio
async def test_twenty_invalid_frames_get_at_most_the_budget_in_replies():
    limiter = WebSocketRateLimiter(max_messages_per_second=10)
    ws = _ws()

    for _ in range(20):
        message, error = await validate_and_parse_message(
            "not json", ws, may_reply=lambda: limiter.check_rate_limit(ws)[0]
        )
        assert message is None and error

    assert _replies(ws) == 10


@pytest.mark.asyncio
async def test_binary_frames_are_metered_too():
    limiter = WebSocketRateLimiter(max_messages_per_second=10)
    ws = _ws()

    for _ in range(20):
        assert await receive_text_frame(ws, lambda: limiter.check_rate_limit(ws)[0]) is None

    assert _replies(ws) == 10


@pytest.mark.asyncio
async def test_without_a_gate_every_rejection_is_still_answered():
    """Existing callers (and tests) that pass no gate keep the old behaviour."""
    ws = _ws()

    await validate_and_parse_message("not json", ws)

    assert _replies(ws) == 1


@pytest.mark.asyncio
async def test_text_frame_is_returned_and_disconnect_raises():
    from fastapi import WebSocketDisconnect

    ws = _ws()
    ws.receive = AsyncMock(return_value={"type": "websocket.receive", "text": '{"type":"ping"}'})
    assert await receive_text_frame(ws, lambda: True) == '{"type":"ping"}'

    ws.receive = AsyncMock(return_value={"type": "websocket.disconnect", "code": 1001})
    with pytest.raises(WebSocketDisconnect):
        await receive_text_frame(ws, lambda: True)


def test_endpoint_limiter_uses_the_shared_constant():
    assert system._rate_limiter.max_messages_per_second == WS_MAX_MESSAGES_PER_SECOND


def test_uvicorn_is_told_to_bound_inbound_frames():
    source = (_BACKEND / "main.py").read_text()

    assert "ws_max_size=WS_MAX_MESSAGE_SIZE" in source
    assert WS_MAX_MESSAGE_SIZE == 64 * 1024
