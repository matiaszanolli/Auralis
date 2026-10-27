#!/usr/bin/env python3

"""
Stream pause/flow gates
~~~~~~~~~~~~~~~~~~~~~~~

Per-WebSocket events the streaming pumps wait on between chunks. They live in
``core`` rather than ``routers.system`` because the pumps are the consumers:
three of them used to import the registries from the router module at call
time, which put a router import inside the audio path and made each pump a
copy of the same four-line gate (#5761). ``routers.system`` now imports the
registries from here and hands them to the WebSocket handlers through
``StreamState``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging

from fastapi import WebSocket

from . import audio_stream_controller as _asc

logger = logging.getLogger(__name__)

#: Upper bound on how long a chunk pump may park on the client's flow gate
#: (#5863). The client's ``buffer_ready`` was evaluated only when the next
#: chunk arrived — but after ``buffer_full`` this very wait is what stops
#: the chunks, so a lost resume signal parked the stream forever. A bound
#: turns an unbounded truncation into a bounded stall plus a log line.
FLOW_GATE_TIMEOUT_S = 30.0

# Per-WebSocket pause events: when clear, streaming loops sleep; when set, they proceed.
# This avoids destroying the streaming task on pause (#2106).
stream_pause_events: dict[str, asyncio.Event] = {}

# Per-WebSocket flow control events: when clear, backend stops sending chunks
# (frontend buffer is full); when set, backend continues streaming.
# Separate from pause events — pause is user-initiated, flow is buffer-driven.
stream_flow_events: dict[str, asyncio.Event] = {}


async def wait_for_stream_gates(websocket: WebSocket) -> None:
    """Block until this connection is neither paused nor flow-controlled.

    The flow gate is bounded (#5863): on timeout, log and resume rather
    than park the stream forever — the client's drain watch or its next
    flow signal re-syncs the buffer state. The pause gate stays unbounded:
    pause is user-initiated and its resume arrives through a separate,
    always-available path (handle_resume / the next play command).
    """
    key = _asc.ws_id(websocket)
    pause_evt = stream_pause_events.get(key)
    if pause_evt is not None:
        await pause_evt.wait()
    flow_evt = stream_flow_events.get(key)
    if flow_evt is not None:
        if flow_evt.is_set():
            return
        try:
            await asyncio.wait_for(flow_evt.wait(), timeout=FLOW_GATE_TIMEOUT_S)
        except TimeoutError:
            logger.warning(
                f"Stream flow gate for {key} did not clear within "
                f"{FLOW_GATE_TIMEOUT_S}s (lost buffer_ready?); resuming delivery (#5863)"
            )
