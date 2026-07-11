"""
WebSocket Playback Command Handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handlers for the three message types that create a new background streaming
task: play_enhanced, play_normal, seek. Extracted verbatim from the
websocket_endpoint dispatch loop in routers/system.py (#4074).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import json
import logging
import math
from typing import Any

from fastapi import WebSocket

from core.audio_stream_controller import ws_id as _ws_id
from websocket.websocket_security import send_error_response

from .context import StreamState, WSDeps

logger = logging.getLogger(__name__)

VALID_PRESETS = ["adaptive", "gentle", "warm", "bright", "punchy"]


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
        old_task.cancel()
        # Await cancellation so the old task releases pause/flow events (#3219)
        try:
            await old_task
        except (asyncio.CancelledError, Exception):
            pass


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

    raw_preset = data.get("preset", "")
    raw_intensity = data.get("intensity")
    preset = raw_preset.lower() if (raw_preset and isinstance(raw_preset, str) and raw_preset.lower() in VALID_PRESETS) else None
    intensity = float(raw_intensity) if (isinstance(raw_intensity, (int, float)) and 0.0 <= raw_intensity <= 1.0) else None

    enhancement_enabled = True
    if deps.get_enhancement_settings is not None:
        settings = deps.get_enhancement_settings()
        enhancement_enabled = settings.get("enabled", True)
        if preset is None:
            preset = settings.get("preset", "adaptive")
        if intensity is None:
            intensity = settings.get("intensity", 1.0)
        logger.info(f"Using enhancement settings (frontend+stored): enabled={enhancement_enabled}, preset={preset}, intensity={intensity}")
    else:
        if preset is None:
            await send_error_response(websocket, "invalid_preset", f"Invalid preset. Must be one of: {', '.join(VALID_PRESETS)}")
            return
        if intensity is None:
            intensity = 1.0
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

    # Deduplicate: if the same track is already streaming, skip
    async with state.active_tasks_lock:
        existing_track = state.active_track_ids.get(ws_id)
        existing_task = state.active_tasks.get(ws_id)
        if (existing_track == track_id and existing_task is not None and not existing_task.done()):
            logger.info(f"Ignoring duplicate play_enhanced for track {track_id} (already streaming on ws {ws_id})")
            return

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
            deps.get_cache_manager,
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
            deps.get_cache_manager,
            track_id=track_id,
            start_position=start_position,
            ws_id=ws_id,
        ))
        state.active_tasks[ws_id] = task
        # Track which track is streaming so subsequent play_enhanced
        # dedup checks see the truth (#3509 / BE-NEW-51).
        state.active_track_ids[ws_id] = track_id
    logger.info(f"Started background normal streaming task for track {track_id}")


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

    # Use WS message values as initial fallback (fixes #2381),
    # then let server-side settings override (fixes #2103).
    preset = data.get("preset", "adaptive")
    intensity = data.get("intensity", 1.0)
    if deps.get_enhancement_settings is not None:
        settings = deps.get_enhancement_settings()
        preset = settings.get("preset", preset)
        intensity = settings.get("intensity", intensity)

    logger.info(f"Received seek: track_id={track_id}, position={position}s, preset={preset}")

    # Pop prior task under lock; cancel and await outside lock to avoid deadlock (fixes #2425, #2430)
    ws_id = _ws_id(websocket)
    async with state.active_tasks_lock:
        for k in [k for k, v in state.active_tasks.items() if v.done()]:
            state.active_tasks.pop(k, None)
        old_task = state.active_tasks.pop(ws_id, None)
    if old_task and not old_task.done():
        logger.info("Cancelling existing streaming task for seek")
        old_task.cancel()
        # Await unconditionally (fixes #3806) — the prior 100ms
        # wait_for/shield let the old task's DSP work (200ms-2s
        # inside asyncio.to_thread) outlive the timeout, so it
        # resumed and sent its own chunk over the same websocket
        # concurrently with the new seek task, interleaving
        # frames. play_enhanced/play_normal already await
        # unconditionally (see above); seek was the outlier. No
        # deadlock risk: the lock was released above this block.
        try:
            await old_task
        except (asyncio.CancelledError, Exception):
            pass

    await websocket.send_text(json.dumps({
        "type": "seek_started",
        "data": {"track_id": track_id, "position": position},
    }))

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
            deps.get_cache_manager,
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
