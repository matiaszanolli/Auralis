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

from fastapi import WebSocket

from . import audio_stream_controller as _asc

# Per-WebSocket pause events: when clear, streaming loops sleep; when set, they proceed.
# This avoids destroying the streaming task on pause (#2106).
stream_pause_events: dict[str, asyncio.Event] = {}

# Per-WebSocket flow control events: when clear, backend stops sending chunks
# (frontend buffer is full); when set, backend continues streaming.
# Separate from pause events — pause is user-initiated, flow is buffer-driven.
stream_flow_events: dict[str, asyncio.Event] = {}


async def wait_for_stream_gates(websocket: WebSocket) -> None:
    """Block until this connection is neither paused nor flow-controlled."""
    key = _asc.ws_id(websocket)
    pause_evt = stream_pause_events.get(key)
    if pause_evt is not None:
        await pause_evt.wait()
    flow_evt = stream_flow_events.get(key)
    if flow_evt is not None:
        await flow_evt.wait()
