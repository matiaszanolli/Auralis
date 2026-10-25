"""
Bounded stream flow gate (#5863)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After ``buffer_full`` the chunk pumps park on ``wait_for_stream_gates`` and
send nothing, so a lost ``buffer_ready`` (rate limiter, dropped socket
frame) parked the stream forever — the rest of the track was never
delivered. The flow gate is now bounded: log and resume.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core import stream_gates  # noqa: E402


def _websocket_with_key(key: str) -> MagicMock:
    ws = MagicMock()
    # ws_id(websocket) resolves through the controller; patch it to the key.
    stream_gates._asc.ws_id = lambda w: key
    return ws


@pytest.mark.asyncio
async def test_set_flow_event_returns_immediately(monkeypatch):
    monkeypatch.setattr(stream_gates, 'FLOW_GATE_TIMEOUT_S', 0.05)
    key = 'ws-set'
    evt = asyncio.Event()
    evt.set()
    monkeypatch.setitem(stream_gates.stream_flow_events, key, evt)

    ws = _websocket_with_key(key)
    await asyncio.wait_for(stream_gates.wait_for_stream_gates(ws), timeout=0.5)


@pytest.mark.asyncio
async def test_never_set_flow_event_resumes_after_the_bound(monkeypatch, caplog):
    monkeypatch.setattr(stream_gates, 'FLOW_GATE_TIMEOUT_S', 0.05)
    key = 'ws-stuck'
    evt = asyncio.Event()  # never set — the lost-buffer_ready case
    monkeypatch.setitem(stream_gates.stream_flow_events, key, evt)

    ws = _websocket_with_key(key)
    with caplog.at_level('WARNING', logger='core.stream_gates'):
        # Must return (not hang) shortly after the bound.
        await asyncio.wait_for(stream_gates.wait_for_stream_gates(ws), timeout=1.0)

    assert any('#5863' in r.message for r in caplog.records), (
        'a bounded stall must be visible in the logs'
    )


@pytest.mark.asyncio
async def test_flow_event_cleared_mid_wait_returns_without_warning(monkeypatch, caplog):
    monkeypatch.setattr(stream_gates, 'FLOW_GATE_TIMEOUT_S', 0.2)
    key = 'ws-late'
    evt = asyncio.Event()
    monkeypatch.setitem(stream_gates.stream_flow_events, key, evt)

    async def clear_soon():
        await asyncio.sleep(0.05)
        evt.set()

    ws = _websocket_with_key(key)
    with caplog.at_level('WARNING', logger='core.stream_gates'):
        await asyncio.wait_for(
            asyncio.gather(stream_gates.wait_for_stream_gates(ws), clear_soon()),
            timeout=1.0,
        )
    assert not any('#5863' in r.message for r in caplog.records)
