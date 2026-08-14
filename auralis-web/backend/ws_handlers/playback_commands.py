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

from core.audio_stream_controller import ws_id as _ws_id
from core.stream_protocol import safe_send_text
from fastapi import WebSocket
from helpers import spawn_background_task
from schemas import (  # single source of truth (#4424, #4600)
    VALID_PRESETS,
    is_valid_intensity,
)
from websocket.websocket_security import send_error_response

from .context import StreamState, WSDeps

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
        old_task.cancel()
        # Await cancellation so the old task releases pause/flow events (#3219)
        try:
            await old_task
        except (asyncio.CancelledError, Exception):
            pass


async def _generate_mastering_recommendation(track_id: int, deps: WSDeps) -> None:
    """Resolve the track path and broadcast its mastering recommendation.

    #4542: RecommendationService.generate_and_broadcast_recommendation was only
    ever scheduled from POST /api/player/load, which the frontend never calls —
    its real playback path is the WS play_enhanced/play_normal commands. The
    recommendation panel therefore showed a loading state for 10s and timed out
    for every track in every session. This is the trigger on the live path.

    Spawned via spawn_background_task by the callers, not FastAPI
    BackgroundTasks: #3553 flagged that running the full audio analysis through
    BackgroundTasks puts it on the event loop. The service already offloads its
    blocking body to a worker thread.

    Never raises into the play path — a failed recommendation must not stop
    playback.
    """
    if deps.get_repository_factory is None or deps.broadcast_manager is None:
        logger.debug(
            "Skipping mastering recommendation: repository factory or broadcast "
            "manager unavailable"
        )
        return

    try:
        repos = deps.get_repository_factory()
        # Sync DB read — keep it off the event loop.
        track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)
        if track is None or not getattr(track, "filepath", None):
            logger.debug(f"No filepath for track {track_id}; skipping recommendation")
            return

        # Imported lazily: services.recommendation_service pulls in the
        # processing stack, and this module is imported during router setup.
        from services.recommendation_service import RecommendationService

        service = RecommendationService(connection_manager=deps.broadcast_manager)
        await service.generate_and_broadcast_recommendation(
            track_id=track_id,
            track_path=track.filepath,
        )
    except Exception:
        logger.exception(
            f"Mastering recommendation failed for track {track_id} (playback unaffected)"
        )


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
    # Third contract for the same quantity, deliberately kept (#4600): an
    # out-of-range/NaN intensity on a *streaming command* falls back to the
    # stored setting rather than 422-ing, because refusing to start playback
    # over a bad slider value is worse than playing at the stored intensity.
    # The REST surfaces reject instead — see EnhancementIntensity in schemas.py.
    # What is NOT acceptable, and was the actual bug, is silent coercion to
    # maximum: `is_valid_intensity` rejects NaN and ±inf, so neither can reach
    # the runtime settings dict from here.
    intensity = float(raw_intensity) if is_valid_intensity(raw_intensity) else None

    enhancement_enabled = True
    if deps.get_enhancement_settings is not None:
        settings = deps.get_enhancement_settings()
        enhancement_enabled = settings.get("enabled", True)
        if preset is None:
            preset = settings.get("preset", "adaptive")
        if intensity is None:
            intensity = settings.get("intensity", 1.0)
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

    # #4542 SIBLING: normal playback needs the trigger too — wiring only the
    # enhanced path would leave the feature dead for unenhanced playback.
    spawn_background_task(
        _generate_mastering_recommendation(track_id, deps),
        name=f"mastering_recommendation:{track_id}",
    )


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

    # Use WS message values as initial fallback (fixes #2381), then let
    # server-side settings override (fixes #2103). The override source is
    # THIS connection's own active stream settings — recorded by
    # handle_play_enhanced — not the process-global enhancement_settings
    # dict (#4742): that global is shared by every connection, so a second
    # connection's play_enhanced used to silently retarget this connection's
    # seek. Fall back to the global only when this connection has no
    # recorded stream yet (e.g. seek arrived before any play_enhanced).
    ws_id = _ws_id(websocket)
    stream_settings = state.active_stream_settings.get(ws_id)

    preset = data.get("preset", "adaptive")
    intensity = data.get("intensity", 1.0)
    if stream_settings is not None:
        preset = stream_settings.get("preset", preset)
        intensity = stream_settings.get("intensity", intensity)
    elif deps.get_enhancement_settings is not None:
        settings = deps.get_enhancement_settings()
        preset = settings.get("preset", preset)
        intensity = settings.get("intensity", intensity)

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
