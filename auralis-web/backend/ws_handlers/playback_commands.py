"""
WebSocket Playback Command Handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handlers for the three message types that create a new background streaming
task: play_enhanced, play_normal, seek. Extracted verbatim from the
websocket_endpoint dispatch loop in routers/system.py (#4074).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import json
import logging
import math
from collections.abc import Mapping
from typing import Any

from core.audio_stream_controller import ws_id as _ws_id
from core.stream_protocol import safe_send_text
from fastapi import WebSocket
from helpers import spawn_background_task
from schemas import (  # single source of truth (#4424, #4600)
    DEFAULT_PRESET,
    VALID_PRESETS,
    is_valid_intensity,
)
from websocket.websocket_security import send_error_response

from .context import StreamState, WSDeps, await_cancelled_task
from .enhancement_params import (
    DEFAULT_INTENSITY,
    _generate_mastering_recommendation,
    resolve_enhancement_params,
)

logger = logging.getLogger(__name__)


async def _cancel_prior_task(ws_id: str, state: StreamState) -> None:
    """Pop the prior task under lock, then cancel and await it OUTSIDE the
    lock (fixes #3828 / BE-WS-2). Awaiting while holding the lock meant the
    old task's own finally-block self-cleanup (which also acquires this same
    lock) hit a CancelledError on its next await and never completed.
    """
    async with state.active_tasks_lock:
        for k in [k for k, v in state.active_tasks.items() if v.done()]:
            state.active_tasks.pop(k, None)
        old_task = state.active_tasks.pop(ws_id, None)
        state.active_track_ids.pop(ws_id, None)
        state.pause_events.pop(ws_id, None)
        state.flow_events.pop(ws_id, None)

    if old_task and not old_task.done():
        logger.info(f"Cancelling existing streaming task for ws {ws_id}")
        # #4815: signal the in-flight chunk DSP to abort BEFORE cancelling
        # the coroutine — task.cancel() only interrupts the coroutine at its
        # next await; the concurrent.futures.Future already running inside
        # STREAM_EXECUTOR does not stop and keeps running unreferenced
        # unless it checks this event itself (chunk_streaming.process_chunk).
        cancel_event = state.chunk_cancel_events.get(ws_id)
        if cancel_event is not None:
            cancel_event.set()
        old_task.cancel()
        # Await cancellation so the old task releases pause/flow events (#3219)
        await await_cancelled_task(old_task, logger)



async def handle_play_enhanced(
    websocket: WebSocket, message: dict[str, Any], state: StreamState, deps: WSDeps
) -> None:
    data = message.get("data", {})
    track_id = data.get("track_id")

    # Validate track_id before launching any background task (#2393)
    if not isinstance(track_id, int) or track_id <= 0:
        logger.warning(f"Invalid track_id in play_enhanced: {track_id!r}")
        await send_error_response(websocket, "invalid_track_id", "track_id must be a positive integer")
        return

    # Explicit client opt-out of the stored-`enabled` gate (#3773).
    force = bool(data.get("force", False))

    # Third contract for the same quantity, deliberately kept (#4600): an
    # out-of-range/NaN intensity on a *streaming command* falls back to the
    # stored setting rather than 422-ing, because refusing to start playback
    # over a bad slider value is worse than playing at the stored intensity.
    # The REST surfaces reject instead — see EnhancementIntensity in schemas/enhancement.py.
    # What is NOT acceptable, and was the actual bug, is silent coercion to
    # maximum: `is_valid_intensity` rejects NaN and ±inf, so neither can reach
    # the runtime settings dict from here. Both rules now live in
    # `resolve_enhancement_params`, shared with handle_seek (#4677).
    settings = deps.get_enhancement_settings() if deps.get_enhancement_settings is not None else None
    preset, intensity = resolve_enhancement_params(data, settings)

    enhancement_enabled = True
    if settings is not None:
        enhancement_enabled = settings.get("enabled", True)
        # The stored dict is the only fallback here and it was already
        # consulted above, so a None at this point means neither source held a
        # valid value — take the module default rather than erroring, matching
        # the pre-#4677 behaviour of `settings.get("preset", "adaptive")`.
        if preset is None:
            preset = DEFAULT_PRESET
        if intensity is None:
            intensity = DEFAULT_INTENSITY
        # Write the accepted values back (#4601). The payload is authoritative
        # here, but nothing ever recorded that, so the REST global kept the OLD
        # preset while the stream ran on the new one. Two readers key off the
        # global and silently went wrong when they diverged:
        #   * GET /api/processing/parameters looks up _last_content_profiles by
        #     preset, a map the running ChunkedAudioProcessor writes under the
        #     STREAM's preset — so it missed and returned hardcoded
        #     `is_default: True` placeholders as though no processing were
        #     happening, which reads as "engine idle" while it is in fact busy;
        #   * _preprocess_upcoming_chunks pre-warmed cache entries for the
        #     global preset/intensity, so every pre-warmed chunk missed.
        # Mutated in place: the dict is shared by reference with the routers
        # (#4409), so rebinding here would be invisible to them.
        settings["preset"] = preset
        settings["intensity"] = intensity
        logger.info(f"Using enhancement settings (frontend+stored): enabled={enhancement_enabled}, preset={preset}, intensity={intensity}")
    else:
        # No stored dict to fall back on: an unresolvable preset is a client
        # bug with nothing to degrade to, so surface it. handle_seek makes the
        # opposite call deliberately — see its own comment.
        if preset is None:
            await send_error_response(websocket, "invalid_preset", f"Invalid preset. Must be one of: {', '.join(VALID_PRESETS)}")
            return
        if intensity is None:
            intensity = DEFAULT_INTENSITY
        logger.warning("Enhancement settings not available, using validated message data")

    start_position = float(data.get("start_position", 0.0) or 0.0)
    if not math.isfinite(start_position):
        start_position = 0.0

    logger.info(
        f"Received play_enhanced: track_id={track_id}, preset={preset}, intensity={intensity}"
        + (f", resume_at={start_position:.1f}s" if start_position > 0 else "")
    )

    if not enhancement_enabled and not force:
        logger.warning(f"Enhancement disabled, rejecting play_enhanced request for track {track_id}")
        try:
            await websocket.send_text(json.dumps({
                "type": "audio_stream_error",
                "data": {
                    "track_id": track_id,
                    "error": "Auto-mastering is currently disabled. Enable it in the enhancement panel to use this feature.",
                    "code": "ENHANCEMENT_DISABLED",
                    "stream_type": "enhanced",
                }
            }))
        except Exception as e:
            logger.error(f"Failed to send enhancement disabled error: {e}")
        return

    ws_id = _ws_id(websocket)

    # Record what THIS connection's stream actually resolved to, so
    # handle_seek can read it back instead of the process-global
    # enhancement_settings dict (#4742) — that global is shared by every
    # connection, so a second connection's play_enhanced used to silently
    # retarget a first connection's subsequent seeks.
    state.active_stream_settings[ws_id] = {
        "preset": preset,
        "intensity": intensity,
        "enabled": enhancement_enabled,
    }

    # Every command is authoritative, including a same-track reissue with a
    # new preset/intensity or resume position. Mirror play_normal by replacing
    # the active task instead of deduplicating solely by track_id (#4726).
    await _cancel_prior_task(ws_id, state)

    async with state.active_tasks_lock:
        # Create pause event for this stream — set = running (#2106)
        pause_event = asyncio.Event()
        pause_event.set()
        state.pause_events[ws_id] = pause_event
        # Create flow control event — set = flowing (not throttled)
        flow_event = asyncio.Event()
        flow_event.set()
        state.flow_events[ws_id] = flow_event
        task = asyncio.create_task(deps.stream_audio(
            websocket,
            deps.get_repository_factory,
            deps.get_enhancement_settings,
            track_id=track_id,
            preset=preset,
            intensity=intensity,
            force=force,
            start_position=start_position,
            ws_id=ws_id,
        ))
        state.active_tasks[ws_id] = task
        state.active_track_ids[ws_id] = track_id
    logger.info(f"Started background streaming task for track {track_id}")

    # #4542: trigger the mastering recommendation on the live play path.
    spawn_background_task(
        _generate_mastering_recommendation(track_id, deps),
        name=f"mastering_recommendation:{track_id}",
    )


async def handle_play_normal(
    websocket: WebSocket, message: dict[str, Any], state: StreamState, deps: WSDeps
) -> None:
    data = message.get("data", {})
    track_id = data.get("track_id")

    # Validate track_id before launching any background task (#2393)
    if not isinstance(track_id, int) or track_id <= 0:
        logger.warning(f"Invalid track_id in play_normal: {track_id!r}")
        await send_error_response(websocket, "invalid_track_id", "track_id must be a positive integer")
        return

    start_position = float(data.get("start_position", 0.0) or 0.0)
    if not math.isfinite(start_position):
        start_position = 0.0

    logger.info(
        f"Received play_normal: track_id={track_id}"
        + (f", resume_at={start_position:.1f}s" if start_position > 0 else "")
    )

    ws_id = _ws_id(websocket)

    await _cancel_prior_task(ws_id, state)

    async with state.active_tasks_lock:
        # Create pause event for this stream — set = running (#2106)
        pause_event = asyncio.Event()
        pause_event.set()
        state.pause_events[ws_id] = pause_event
        # Create flow control event — set = flowing (not throttled)
        flow_event = asyncio.Event()
        flow_event.set()
        state.flow_events[ws_id] = flow_event
        task = asyncio.create_task(deps.stream_normal(
            websocket,
            deps.get_repository_factory,
            track_id=track_id,
            start_position=start_position,
            ws_id=ws_id,
        ))
        state.active_tasks[ws_id] = task
        # Track which track is streaming so subsequent play_enhanced
        # dedup checks see the truth (#3509 / BE-NEW-51).
        state.active_track_ids[ws_id] = track_id
    logger.info(f"Started background normal streaming task for track {track_id}")

    # #4542 SIBLING: normal playback needs the trigger too — wiring only the
    # enhanced path would leave the feature dead for unenhanced playback.
    spawn_background_task(
        _generate_mastering_recommendation(track_id, deps),
        name=f"mastering_recommendation:{track_id}",
    )


