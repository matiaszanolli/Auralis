"""
Enhancement toggle / preset / intensity / status handlers (split from enhancement.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from fastapi import Depends
from schemas import DEFAULT_PRESET
from typing import Any
from websocket.outbound_messages import broadcast_typed
import asyncio

from .dependencies import with_error_handling
from .enhancement_deps import _get_connection_manager, _get_enhancement_settings, _get_streamlined_cache, _get_player_state_manager, _get_repository_factory
from .enhancement_models import SetIntensityRequest, SetPresetRequest, ToggleEnhancementRequest
from .enhancement_prewarm import _maybe_prewarm_upcoming_chunks

logger = logging.getLogger(__name__)


async def _persist_enhancement_setting(repos: Any, fields: dict[str, Any]) -> None:
    """Write a live enhancement-setting change through to the DB (#4587) —
    the runtime-to-DB half of keeping the Settings dialog and the
    Enhancement Panel in sync. ``fields`` uses ``UserSettings`` column names
    (``auto_enhance``/``default_preset``/``enhancement_intensity``), not the
    runtime dict's shorter ``enabled``/``preset``/``intensity`` keys.

    Tolerant of failure, same as ``settings.py``'s ``_notify_scanner()``: the
    runtime change these callers already applied is the primary effect and
    must not be undone by a DB hiccup — a failed persist just means the
    change won't survive the next restart, which is the pre-fix behaviour,
    not a new regression.
    """
    try:
        await asyncio.to_thread(repos.settings.update_settings, fields)
    except Exception as exc:
        logger.warning(f"Failed to persist enhancement setting {fields}: {exc}")


@with_error_handling("toggle enhancement")
async def toggle_enhancement(
    body: ToggleEnhancementRequest,
    enhancement_settings: dict[str, Any] = Depends(_get_enhancement_settings),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
    repos: Any = Depends(_get_repository_factory),
) -> dict[str, Any]:
    """
    Enable or disable real-time audio enhancement.

    When enabling mid-playback, automatically pre-processes upcoming chunks
    in the background to prevent audio stopping.

    Args:
        enabled: Boolean to enable/disable enhancement

    Returns:
        dict: Status message and current settings

    Raises:
        HTTPException: If toggling fails
    """
    old_enabled = enhancement_settings.get("enabled")
    enabled = body.enabled
    enhancement_settings["enabled"] = enabled

    # If enabling enhancement mid-playback, pre-process upcoming chunks in
    # background (#2296) so the client doesn't hit an on-demand processing gap.
    if enabled:
        _maybe_prewarm_upcoming_chunks(enhancement_settings, player_state_manager)

    # #4587: persist so an Enhancement Panel change survives a backend
    # restart — this endpoint previously only mutated the runtime dict, so
    # the next startup's seed_enhancement_settings() silently reverted it.
    if repos is not None and old_enabled != enabled:
        await _persist_enhancement_setting(repos, {"auto_enhance": enabled})

    # Broadcast to all clients
    await broadcast_typed(
        connection_manager,
        "enhancement_settings_changed",
        {
            "enabled": enabled,
            "preset": enhancement_settings["preset"],
            "intensity": enhancement_settings["intensity"],
        },
    )

    logger.info(f"Enhancement {'enabled' if enabled else 'disabled'}")
    return {
        "message": f"Enhancement {'enabled' if enabled else 'disabled'}",
        "settings": enhancement_settings
    }


@with_error_handling("change preset")
async def set_enhancement_preset(
    body: SetPresetRequest,
    enhancement_settings: dict[str, Any] = Depends(_get_enhancement_settings),
    buffer_manager: Any = Depends(_get_streamlined_cache),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
    repos: Any = Depends(_get_repository_factory),
) -> dict[str, Any]:
    """
    Change the enhancement preset.

    Args:
        preset: Preset name (only 'adaptive' is valid; see schemas.VALID_PRESETS)

    Returns:
        dict: Status message and current settings

    Raises:
        HTTPException: If preset is invalid or change fails
    """
    preset = body.preset  # already validated and lowercased by SetPresetRequest
    old_preset = enhancement_settings.get("preset")
    enhancement_settings["preset"] = preset

    # Update streamlined cache manager for branch prediction learning
    if buffer_manager and player_state_manager and old_preset != preset:
        state = player_state_manager.get_state()
        # Only update if we have a current track
        if state.current_track:
            await buffer_manager.update_position(
                track_id=state.current_track.id,
                position=state.current_time,
                preset=preset,
                intensity=enhancement_settings["intensity"]
            )
            logger.info(f"🎯 Buffer manager learned preset switch: {old_preset} → {preset}")

    # Pre-process upcoming chunks at the new preset so a mid-playback preset
    # change doesn't hit an on-demand processing gap — same treatment
    # toggle_enhancement's enable path already gets (#4425). Only when
    # enhancement is the active audio path and the preset actually changed.
    if enhancement_settings.get("enabled") and old_preset != preset:
        _maybe_prewarm_upcoming_chunks(enhancement_settings, player_state_manager)

    # NOTE: We keep the old preset cached for instant toggling back
    # Proactive buffering will handle caching the new preset in background
    # This prevents the 2-5s delay when switching presets
    logger.info(f"⚡ Preset switched instantly: {old_preset} → {preset} (cache preserved)")

    # #4587: persist so this survives a backend restart — see toggle_enhancement.
    if repos is not None and old_preset != preset:
        await _persist_enhancement_setting(repos, {"default_preset": preset})

    # Broadcast to all clients
    await broadcast_typed(
        connection_manager,
        "enhancement_settings_changed",
        {
            "preset": preset,
            "enabled": enhancement_settings["enabled"],
            "intensity": enhancement_settings["intensity"],
        },
    )

    logger.info(f"Enhancement preset changed to: {preset}")
    return {
        "message": f"Preset changed to {preset}",
        "settings": enhancement_settings
    }


@with_error_handling("set intensity")
async def set_enhancement_intensity(
    body: SetIntensityRequest,
    enhancement_settings: dict[str, Any] = Depends(_get_enhancement_settings),
    buffer_manager: Any = Depends(_get_streamlined_cache),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
    repos: Any = Depends(_get_repository_factory),
) -> dict[str, Any]:
    """
    Adjust the enhancement intensity.

    Args:
        body: JSON body with intensity value between 0.0 and 1.0 (clamped)

    Returns:
        dict: Status message and current settings

    Raises:
        HTTPException: If intensity change fails
    """
    intensity = body.intensity  # already clamped by SetIntensityRequest
    old_intensity = enhancement_settings.get("intensity")
    enhancement_settings["intensity"] = intensity

    preset = enhancement_settings.get("preset", DEFAULT_PRESET)

    # Notify streamlined cache manager so pre-buffered chunks at the old
    # intensity are replaced — mirrors the same call in set_enhancement_preset
    # (fixes #2504).
    if buffer_manager and player_state_manager and old_intensity != intensity:
        state = player_state_manager.get_state()
        if state.current_track:
            await buffer_manager.update_position(
                track_id=state.current_track.id,
                position=state.current_time,
                preset=preset,
                intensity=intensity
            )
            logger.info(f"🎯 Buffer manager updated for intensity switch: {old_intensity} → {intensity}")

    # Pre-process upcoming chunks at the new intensity so a mid-playback
    # intensity change doesn't hit an on-demand processing gap — same
    # treatment toggle_enhancement's enable path already gets (#4425). Only
    # when enhancement is the active audio path and intensity actually changed.
    if enhancement_settings.get("enabled") and old_intensity != intensity:
        _maybe_prewarm_upcoming_chunks(enhancement_settings, player_state_manager)

    # #4587: persist so this survives a backend restart — see toggle_enhancement.
    if repos is not None and old_intensity != intensity:
        await _persist_enhancement_setting(repos, {"enhancement_intensity": intensity})

    # Broadcast to all clients
    await broadcast_typed(
        connection_manager,
        "enhancement_settings_changed",
        {
            "intensity": intensity,
            "enabled": enhancement_settings["enabled"],
            "preset": enhancement_settings["preset"],
        },
    )

    logger.info(f"Enhancement intensity changed to: {intensity}")
    return {
        "message": f"Intensity set to {intensity}",
        "settings": enhancement_settings
    }


@with_error_handling("get enhancement status")
async def get_enhancement_status(
    enhancement_settings: dict[str, Any] = Depends(_get_enhancement_settings),
) -> dict[str, Any]:
    """
    Get current enhancement settings.

    Returns:
        dict: Current enhancement settings (enabled, preset, intensity)
    """
    return enhancement_settings
