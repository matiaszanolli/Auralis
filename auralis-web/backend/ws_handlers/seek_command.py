"""
The WS seek command handler (#6269).

Split out of playback_commands.py (#6269); handle_seek is a separate
command from the two play handlers and shares only the prior-task
cancellation helper, which it imports back.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import math
from typing import Any

from core.audio_stream_controller import ws_id as _ws_id
from core.stream_protocol import safe_send_text
from fastapi import WebSocket
from helpers import spawn_background_task
from schemas import DEFAULT_PRESET  # single source of truth (#4424, #4600)
from websocket.websocket_security import send_error_response

from .context import StreamState, WSDeps
from .enhancement_params import DEFAULT_INTENSITY, resolve_enhancement_params
from .playback_commands import _cancel_prior_task

logger = logging.getLogger(__name__)

async def handle_seek(
    websocket: WebSocket, message: dict[str, Any], state: StreamState, deps: WSDeps
) -> None:
    data = message.get("data", {})
    track_id = data.get("track_id")
    position = data.get("position", 0)

    # Validate before launching any background task (#2393)
    if not isinstance(track_id, int) or track_id <= 0:
        logger.warning(f"Invalid track_id in seek: {track_id!r}")
        await send_error_response(websocket, "invalid_track_id", "track_id must be a positive integer")
        return

    if not isinstance(position, (int, float)) or not math.isfinite(position) or position < 0:
        logger.warning(f"Invalid seek position: {position!r}")
        await send_error_response(websocket, "invalid_seek_position", "position must be a non-negative number")
        return

    # Same precedence as handle_play_enhanced, via the same helper (#4677).
    # These two handlers used to resolve the same quantity with opposite
    # rules: a valid preset on the seek frame was discarded unconditionally
    # (the fallback dict always carries a "preset" key), so scrubbing could
    # re-master the track with a preset the listener never chose, and the
    # no-fallback branch forwarded the client string with no VALID_PRESETS
    # check at all. The client payload is authoritative when valid.
    #
    # Fallback order, for whatever the payload does not supply: THIS
    # connection's own active stream settings — recorded by
    # handle_play_enhanced — before the process-global enhancement_settings
    # dict (#4742). That global is shared by every connection, so a second
    # connection's play_enhanced used to silently retarget this connection's
    # seek; the global is consulted only when this connection has no recorded
    # stream yet (e.g. a seek arriving before any play_enhanced).
    #
    # Unlike play_enhanced, an unresolvable preset defaults here instead of
    # erroring. Refusing to scrub over a bad preset value ends playback at the
    # seek point, which is the same trade #4600 already settled for intensity
    # on streaming commands: degrade, do not reject.
    ws_id = _ws_id(websocket)
    stream_settings = state.active_stream_settings.get(ws_id)
    global_settings = (
        deps.get_enhancement_settings() if deps.get_enhancement_settings is not None else None
    )

    preset, intensity = resolve_enhancement_params(data, stream_settings, global_settings)
    if preset is None:
        preset = DEFAULT_PRESET
    if intensity is None:
        intensity = DEFAULT_INTENSITY

    logger.info(f"Received seek: track_id={track_id}, position={position}s, preset={preset}")

    # #4704: use the shared helper rather than open-coding the teardown.
    # This block popped only `active_tasks`, leaving `active_track_ids`,
    # `pause_events` and `flow_events` pointing at the superseded stream's
    # objects for the whole cancel-and-await window. Nothing broke today
    # because the three are re-registered below, but a divergent copy of a
    # lock-ordered teardown is the shape that produced #3828 / #3522 / #4364.
    # #4364 gave handle_stop the same treatment; seek was the last outlier.
    #
    # The helper preserves both invariants this site depended on: pop under
    # `active_tasks_lock`, then cancel and await OUTSIDE it (#2425/#2430/#3828 —
    # awaiting under the lock is the original deadlock), and await
    # unconditionally (#3806 — the prior 100 ms wait_for/shield let the old
    # task's 200 ms-2 s DSP work outlive the timeout, so it resumed and
    # interleaved chunks with the new seek task on the same websocket).
    #
    # It deliberately does NOT clear `active_stream_settings`: seek reads that
    # snapshot above to inherit the running stream's preset/intensity (#4742),
    # and the new task inherits the same connection's settings. Only
    # handle_stop clears it, because a stop ends the stream outright.
    await _cancel_prior_task(ws_id, state)

    await safe_send_text(websocket, {
        "type": "seek_started",
        "data": {"track_id": track_id, "position": position},
    })

    # #5075 (regression of #4742): unlike preset/intensity above, `enabled`
    # must always come from the LIVE enhancement_settings dict, not this
    # connection's stream_settings snapshot. The enhanced loop selected below
    # re-checks the live global on every chunk (the #2866 guard in
    # stream_seek.py) — resolving a stale `enabled=True` snapshot here while
    # the live global has since been toggled False starts an enhanced
    # stream that breaks on chunk 0 and delivers silent zero-length audio.
    # preset/intensity don't have this problem: nothing re-checks them
    # mid-stream, so the per-connection snapshot from #4742 stays correct
    # and is left unchanged for those two fields.
    enhancement_enabled = True
    if deps.get_enhancement_settings is not None:
        enhancement_enabled = deps.get_enhancement_settings().get("enabled", True)

    # Reset pause/flow-control events AND register the new seek task
    # atomically — fixes #3522 / BE-NEW-64 (prior code did the event
    # replacement outside the lock, leaving a torn-state window).
    async with state.active_tasks_lock:
        pause_event = asyncio.Event()
        pause_event.set()
        state.pause_events[ws_id] = pause_event
        flow_event = asyncio.Event()
        flow_event.set()
        state.flow_events[ws_id] = flow_event
        task = asyncio.create_task(deps.stream_from_position(
            websocket,
            deps.get_repository_factory,
            deps.get_enhancement_settings,
            track_id=track_id,
            preset=preset,
            intensity=intensity,
            position=position,
            enhancement_enabled=enhancement_enabled,
            ws_id=ws_id,
        ))
        state.active_tasks[ws_id] = task
        state.active_track_ids[ws_id] = track_id
    logger.info(f"Started seek streaming task for track {track_id} at {position}s")
