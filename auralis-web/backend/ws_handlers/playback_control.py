"""
WebSocket Playback Control Handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handlers for message types that control an already-running streaming task:
pause, resume, stop, buffer_full, buffer_ready. Extracted verbatim from the
websocket_endpoint dispatch loop in routers/system.py (#4074).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging

from fastapi import WebSocket

from core.audio_stream_controller import ws_id as _ws_id
from core.stream_protocol import safe_send_text

from .context import StreamState, await_cancelled_task

logger = logging.getLogger(__name__)


async def handle_pause(websocket: WebSocket, state: StreamState) -> None:
    logger.info("Received pause command via WebSocket")
    ws_id = _ws_id(websocket)
    pause_evt = state.pause_events.get(ws_id)
    if pause_evt is not None:
        pause_evt.clear()
        logger.info("Paused streaming task (event cleared)")
    # Use {state} shape the frontend type expects (#3503 / BE-NEW-45).
    await safe_send_text(websocket, {"type": "playback_paused", "data": {"state": "paused"}})


async def handle_resume(websocket: WebSocket, state: StreamState) -> None:
    logger.info("Received resume command via WebSocket")
    ws_id = _ws_id(websocket)
    pause_evt = state.pause_events.get(ws_id)
    if pause_evt is not None:
        pause_evt.set()
        logger.info("Resumed streaming task (event set)")
    await safe_send_text(websocket, {"type": "playback_resumed", "data": {"state": "playing"}})


async def handle_buffer_full(websocket: WebSocket, state: StreamState) -> None:
    ws_id = _ws_id(websocket)
    flow_evt = state.flow_events.get(ws_id)
    if flow_evt is not None:
        flow_evt.clear()
        logger.debug("Flow control: paused (buffer_full)")


async def handle_buffer_ready(websocket: WebSocket, state: StreamState) -> None:
    ws_id = _ws_id(websocket)
    flow_evt = state.flow_events.get(ws_id)
    if flow_evt is not None:
        flow_evt.set()
        logger.debug("Flow control: resumed (buffer_ready)")


async def handle_stop(websocket: WebSocket, state: StreamState) -> None:
    logger.info("Received stop command via WebSocket")
    ws_id = _ws_id(websocket)
    # #4704 SIBLING, deliberately NOT routed through
    # playback_commands._cancel_prior_task, unlike handle_seek:
    #   * this also clears `active_stream_settings`, which the helper must not
    #     touch — seek and play re-use that snapshot for the successor stream
    #     (#4742), whereas a stop ends the stream outright;
    #   * the helper additionally sweeps completed tasks for OTHER ws ids,
    #     which stop has no reason to do;
    #   * `playback_control` does not import from `playback_commands`, and
    #     reaching for a sibling module's private helper to save six lines
    #     would couple the two for less than it costs.
    # Consolidating all three teardown sites behind one shared module is a
    # reasonable follow-up, but it is a behaviour change for this handler and
    # is out of scope for a consistency fix.
    async with state.active_tasks_lock:
        task = state.active_tasks.pop(ws_id, None)
        # Also clear the per-ws event/track registries so a stop with no
        # subsequent play/seek doesn't leave stale entries dangling until
        # disconnect — matching _cancel_prior_task / teardown_connection (#4364).
        state.active_track_ids.pop(ws_id, None)
        state.pause_events.pop(ws_id, None)
        state.flow_events.pop(ws_id, None)
        state.active_stream_settings.pop(ws_id, None)  # #4742
        # #4815: same sibling treatment as _cancel_prior_task — pop while
        # holding the lock, then set() outside it (below), so an in-flight
        # chunk DSP call aborts instead of running to completion unreferenced.
        cancel_event = state.chunk_cancel_events.pop(ws_id, None)
    if cancel_event is not None:
        cancel_event.set()
    if task and not task.done():
        task.cancel()
        await await_cancelled_task(task, logger)
        logger.info("Cancelled active streaming task")
    await safe_send_text(websocket, {"type": "playback_stopped", "data": {"state": "stopped"}})
