"""Registering one connection's stream, and the two halves of tearing it down (#6292, #6625).

`attach_stream` is the one registration path for play_enhanced, play_normal and seek: it creates the
task and records it with fresh pause/flow events in a single `active_tasks_lock` section (#3522).


`playback_commands._cancel_prior_task` (play/seek), `playback_control.handle_stop` and
`connection.teardown_connection` each did "pop the task and per-ws registries under the lock, set the
chunk cancel token, cancel, await" by hand, with deliberate differences, and every new registry or
token step (#4364, #4742, #4815) had to be applied at all three. The differences are parameters here.

The helper takes no locks and awaits nothing: the caller pops under `active_tasks_lock`, then cancels
and awaits OUTSIDE it, in whatever lock shape the site needs (an await under the lock deadlocks the
dying task's own cleanup, #3828; stop awaits outside the process-wide transition lock, #5319).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import threading
from collections.abc import Callable, Coroutine
from typing import Any

from core.stream_gates import FlowGate

from .context import StreamState


async def attach_stream(
    state: StreamState,
    ws_id: str,
    track_id: int,
    start: Callable[[], Coroutine[Any, Any, Any]],
) -> None:
    """Start ``start()`` as ``ws_id``'s stream task and register it; call after the prior task is gone.

    The pause and flow events are replaced and the task created and recorded under one hold of
    ``state.active_tasks_lock`` (#3522): an event swap outside it left a window in which a pause or a
    flow toggle reached the dying stream's events instead of the new one's. Both start set (running,
    flowing; #2106).
    """
    async with state.active_tasks_lock:
        pause_event = asyncio.Event()
        pause_event.set()
        state.pause_events[ws_id] = pause_event
        flow_event = FlowGate()  # counts buffer_full re-assertions (#6553)
        flow_event.set()
        state.flow_events[ws_id] = flow_event
        state.active_tasks[ws_id] = asyncio.create_task(start())
        state.active_track_ids[ws_id] = track_id


def detach_stream(
    state: StreamState,
    ws_id: str,
    *,
    clear_settings: bool,
    pop_cancel_event: bool,
) -> tuple['asyncio.Task[Any] | None', threading.Event | None]:
    """Remove ``ws_id``'s stream registries; call with ``state.active_tasks_lock`` held.

    ``clear_settings`` drops the `active_stream_settings` snapshot: a stop or a disconnect ends the
    stream, whereas a play or seek reuses the snapshot for its successor (#4742). ``pop_cancel_event``
    removes the chunk cancel token too; a replaced stream leaves it for its own finally to remove, as
    the successor may already own the slot (#4815).
    """
    task = state.active_tasks.pop(ws_id, None)
    state.active_track_ids.pop(ws_id, None)
    state.pause_events.pop(ws_id, None)
    state.flow_events.pop(ws_id, None)
    if clear_settings:
        state.active_stream_settings.pop(ws_id, None)
    cancel_event = (
        state.chunk_cancel_events.pop(ws_id, None) if pop_cancel_event
        else state.chunk_cancel_events.get(ws_id)
    )
    return task, cancel_event


def signal_cancel(
    task: 'asyncio.Task[Any] | None', cancel_event: threading.Event | None
) -> 'asyncio.Task[Any] | None':
    """Abort the stream's DSP and cancel its task; returns the task when the caller must await it.

    The token is set BEFORE ``task.cancel()`` (#4815): cancelling only interrupts the coroutine at its
    next await, while a chunk already running in the executor keeps going unreferenced unless it checks
    the token itself. A task that already finished needs no await.
    """
    if cancel_event is not None:
        cancel_event.set()
    if task is None or task.done():
        return None
    task.cancel()
    return task
