"""
WebSocket Playback Control Handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handlers for message types that control an already-running streaming task:
pause, resume, stop, buffer_full, buffer_ready. Extracted verbatim from the
websocket_endpoint dispatch loop in routers/system.py (#4074).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging

from core.audio_stream_controller import ws_id as _ws_id
from core.stream_protocol import safe_send_text
from fastapi import WebSocket
from services.playback_event_sequencer import playback_event_sequencer

from core.task_cancellation import await_cancelled_task

from .context import StreamState
from .stream_cancel import detach_stream, signal_cancel

logger = logging.getLogger(__name__)


async def handle_pause(websocket: WebSocket, state: StreamState) -> None:
    logger.info("Received pause command via WebSocket")
    ws_id = _ws_id(websocket)
    async with playback_event_sequencer.transition_lock:
        pause_evt = state.pause_events.get(ws_id)
        if pause_evt is not None:
            pause_evt.clear()
            logger.info("Paused streaming task (event cleared)")
        event_seq = playback_event_sequencer.next_transport_seq()
    # Use {state} shape the frontend type expects (#3503 / BE-NEW-45).
    await safe_send_text(
        websocket,
        {"type": "playback_paused", "data": {"state": "paused", "seq": event_seq}},
    )


async def handle_resume(websocket: WebSocket, state: StreamState) -> None:
    logger.info("Received resume command via WebSocket")
    ws_id = _ws_id(websocket)
    async with playback_event_sequencer.transition_lock:
        pause_evt = state.pause_events.get(ws_id)
        if pause_evt is not None:
            pause_evt.set()
            logger.info("Resumed streaming task (event set)")
        event_seq = playback_event_sequencer.next_transport_seq()
    await safe_send_text(
        websocket,
        {"type": "playback_resumed", "data": {"state": "playing", "seq": event_seq}},
    )


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
    # Not routed through playback_commands._cancel_prior_task: a stop also clears the settings
    # snapshot and awaits outside the process-wide transition lock (#4704, #5319). The pop and the
    # cancel-token step are the shared stream_cancel helpers (#6292).
    async with playback_event_sequencer.transition_lock:
        async with state.active_tasks_lock:
            task, cancel_event = detach_stream(state, ws_id, clear_settings=True, pop_cancel_event=True)
        task = signal_cancel(task, cancel_event)
        event_seq = playback_event_sequencer.next_transport_seq()
    # #5319: await the cancelled task's teardown OUTSIDE transition_lock. That
    # lock is process-wide — every WS connection's pause/resume/stop and the
    # REST PlaybackService contend on it — and the teardown is unbounded
    # (stream_enhanced's `to_thread(processor.close)` queues on IO_EXECUTOR).
    # The stop's position in the transport order is fixed by the seq drawn
    # above; the dying task draws no seq of its own, so nothing needs the lock
    # past this point. Still awaited before `playback_stopped` is sent, so the
    # old stream has quiesced on this socket by the time the client hears it.
    if task is not None:
        await await_cancelled_task(task, logger)
        logger.info("Cancelled active streaming task")
    await safe_send_text(
        websocket,
        {"type": "playback_stopped", "data": {"state": "stopped", "seq": event_seq}},
    )
