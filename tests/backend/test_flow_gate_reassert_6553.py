"""The bounded flow gate stops forcing chunks to a client that re-asserts buffer_full (#6553).

#5863 bounded the wait for buffer_ready so a LOST resume signal could not park
the stream forever. A user pause is client-side only, so a paused client never
drains and never sends buffer_ready; the bound then fed it one chunk per timeout
until its PCM ring overflowed. A client that re-asserts buffer_full after a
forced chunk is alive and full: the gate now keeps waiting for its buffer_ready.
A client that stays silent still gets the #5863 forced chunk.
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from core import stream_gates  # noqa: E402
from core.audio_stream_controller import ws_id  # noqa: E402

TIMEOUT = 0.05


@pytest.fixture
def gate(monkeypatch):
    monkeypatch.setattr(stream_gates, "FLOW_GATE_TIMEOUT_S", TIMEOUT)
    websocket = SimpleNamespace()
    flow = stream_gates.FlowGate()
    flow.set()
    stream_gates.stream_flow_events[ws_id(websocket)] = flow
    yield websocket, flow
    stream_gates.stream_flow_events.pop(ws_id(websocket), None)


async def _returns_within(websocket, seconds):
    try:
        await asyncio.wait_for(stream_gates.wait_for_stream_gates(websocket), timeout=seconds)
        return True
    except TimeoutError:
        return False


@pytest.mark.asyncio
async def test_a_paused_client_that_reasserts_full_gets_no_more_forced_chunks(gate):
    websocket, flow = gate
    flow.note_full()
    assert await _returns_within(websocket, TIMEOUT * 4)  # the one #5863 forced chunk

    flow.note_full()  # that chunk landed in a still-full ring: the client says so
    assert not await _returns_within(websocket, TIMEOUT * 6), "kept trickling to a paused client"


@pytest.mark.asyncio
async def test_a_silent_client_still_gets_the_5863_forced_chunk_each_timeout(gate):
    websocket, flow = gate
    flow.note_full()  # then its buffer_ready is lost: no further signals
    assert await _returns_within(websocket, TIMEOUT * 4)
    assert await _returns_within(websocket, TIMEOUT * 4)


@pytest.mark.asyncio
async def test_buffer_ready_releases_the_held_gate_and_starts_a_fresh_episode(gate):
    websocket, flow = gate
    flow.note_full()
    assert await _returns_within(websocket, TIMEOUT * 4)
    flow.note_full()

    waiter = asyncio.ensure_future(stream_gates.wait_for_stream_gates(websocket))
    await asyncio.sleep(TIMEOUT * 3)
    assert not waiter.done()
    flow.note_ready()
    await asyncio.wait_for(waiter, timeout=1)

    flow.note_full()  # the next pause episode again forces one chunk on timeout
    assert await _returns_within(websocket, TIMEOUT * 4)
