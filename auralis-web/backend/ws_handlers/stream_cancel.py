"""The two halves of tearing down one connection's stream, shared by the three sites (#6292).

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
from typing import Any

from .context import StreamState


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
