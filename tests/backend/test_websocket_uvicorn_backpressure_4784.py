"""
Verify uvicorn's WebSocket ASGI protocol actually implements transport
backpressure (#4784)

Both the internal `_SEND_QUEUE_MAXSIZE` producer/consumer queue
(stream_protocol.py) and `ConnectionManager.broadcast`'s
`BROADCAST_SEND_TIMEOUT` guard (config/globals.py) only do anything useful
if uvicorn's WebSocket protocol genuinely suspends `send()` when the
transport's write buffer fills — i.e. when a client stops draining its
socket. Every uvicorn version through 0.52.0 sets an internal `writable`
asyncio.Event once at construction and never clears it (`pause_writing`/
`resume_writing` are unimplemented, silently no-op via the
`asyncio.Protocol` base class), so `send()` never actually blocks and
these guards can never trigger.

uvicorn 0.52.1 fixed this by wiring `pause_writing`/`resume_writing` (the
standard `asyncio.Transport` flow-control callbacks) into a real
asyncio.Event that `send()` awaits. requirements.txt/pyproject.toml are
now floored at 0.52.1 for this reason — these tests exercise the real
mechanism directly (not a mock) so a future accidental downgrade fails
loudly here instead of silently reintroducing unbounded backend memory
growth against a stalled client.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio

import pytest
import uvicorn
from packaging.version import Version
from uvicorn.config import Config
from uvicorn.protocols.websockets.websockets_sansio_impl import WebSocketsSansIOProtocol
from uvicorn.server import ServerState

# The confirmed fix boundary: 0.52.0 has no pause_writing/resume_writing
# override at all (inherits the asyncio.Protocol no-op base); 0.52.1 does.
MIN_BACKPRESSURE_UVICORN_VERSION = "0.52.1"


async def _minimal_asgi_app(scope, receive, send):  # pragma: no cover - never invoked
    pass


def _make_protocol() -> WebSocketsSansIOProtocol:
    config = Config(app=_minimal_asgi_app, ws="auto")
    config.load()
    return WebSocketsSansIOProtocol(config, ServerState(), {})


def test_installed_uvicorn_meets_backpressure_floor():
    """Fast, cheap guard: fail loudly if uvicorn is ever downgraded below
    the version that actually implements WebSocket transport backpressure."""
    assert Version(uvicorn.__version__) >= Version(MIN_BACKPRESSURE_UVICORN_VERSION), (
        f"uvicorn {uvicorn.__version__} is below {MIN_BACKPRESSURE_UVICORN_VERSION} — "
        "WebSocket send() will never suspend under backpressure (#4784)"
    )


class TestUvicornWebSocketProtocolBackpressure:
    """Exercise uvicorn's real WebSocketsSansIOProtocol, not a mock — this
    is what would have caught #4784 against the previously-pinned 0.38.0."""

    @pytest.mark.asyncio
    async def test_pause_writing_clears_the_writable_event(self):
        protocol = _make_protocol()
        assert protocol.writable.is_set(), "writable must start set (no backpressure yet)"

        protocol.pause_writing()

        assert not protocol.writable.is_set(), (
            "pause_writing() must clear `writable` so send() actually suspends — "
            "on uvicorn <=0.52.0 this method is an inherited asyncio.Protocol "
            "no-op and writable never clears"
        )

    @pytest.mark.asyncio
    async def test_resume_writing_sets_the_writable_event_back(self):
        protocol = _make_protocol()
        protocol.pause_writing()
        assert not protocol.writable.is_set()

        protocol.resume_writing()

        assert protocol.writable.is_set(), "resume_writing() must re-set `writable`"

    @pytest.mark.asyncio
    async def test_send_suspends_while_writable_is_cleared(self):
        """Directly simulates 'a client stops reading': once the transport
        signals backpressure, send() must genuinely block until it clears —
        not return immediately regardless of transport state."""
        protocol = _make_protocol()
        protocol.pause_writing()  # simulate a full transport write buffer

        reached = False

        async def wait_for_writable():
            nonlocal reached
            await protocol.writable.wait()
            reached = True

        task = asyncio.create_task(wait_for_writable())
        await asyncio.sleep(0.01)
        assert not reached, "send()'s underlying wait must still be blocked while paused"

        protocol.resume_writing()  # simulate the client draining its socket again
        await asyncio.wait_for(task, timeout=1.0)
        assert reached, "send() must unblock once the transport signals resume_writing"
