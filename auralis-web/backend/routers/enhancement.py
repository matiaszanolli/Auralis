"""
Enhancement Router
~~~~~~~~~~~~~~~~~~

Handles real-time audio enhancement settings for the player.

Endpoints:
- POST /api/player/enhancement/toggle - Enable/disable enhancement
- POST /api/player/enhancement/preset - Change enhancement preset
- POST /api/player/enhancement/intensity - Adjust enhancement intensity
- GET /api/player/enhancement/status - Get current enhancement settings

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import os
import time
from collections import OrderedDict
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from .dependencies import with_error_handling
from .errors import NotFoundError
from pydantic import BaseModel, field_validator

from core.chunk_boundaries import (  # single source of truth (#2564)
    chunk_for_position,
    content_chunk_count,
)
from helpers import spawn_background_task
from schemas import (
    EnhancementIntensity,
    EnhancementPresetLiteral,
    MasteringRecommendationResponse,
)

logger = logging.getLogger(__name__)

# TTL cache for mastering recommendations so repeated calls for the same
# (track_id, confidence_threshold) don't re-run the full audio analysis
# (~1-5 s CPU per call).  Entries expire after 60 s (fixes #3865 / BE-RH-20).
# Format: key -> (expiry_monotonic, result_dict)
#
# Bounded and self-purging (#4657): TTL-only expiry was checked on read but
# entries were never deleted, so the dict grew for the life of the process at
# a rate of (tracks browsed x distinct thresholds). Expired keys are dropped on
# insert and the cache is capped in FIFO order, so a long desktop session over
# a large library cannot grow it without limit.
_recommendation_cache: OrderedDict[tuple[int, float], tuple[float, dict[str, Any]]] = OrderedDict()
_RECOMMENDATION_TTL_S: float = 60.0
_RECOMMENDATION_CACHE_MAX: int = 256


def _store_recommendation(key: tuple[int, float], expiry: float, value: dict[str, Any]) -> None:
    """Insert a recommendation, purging expired entries and enforcing the cap."""
    now = time.monotonic()
    for stale_key in [k for k, (exp, _) in _recommendation_cache.items() if exp <= now]:
        del _recommendation_cache[stale_key]

    _recommendation_cache[key] = (expiry, value)
    _recommendation_cache.move_to_end(key)

    while len(_recommendation_cache) > _RECOMMENDATION_CACHE_MAX:
        _recommendation_cache.popitem(last=False)

# EnhancementPresetLiteral is the single source of truth in schemas.py (#4424),
# imported above. It drives OpenAPI so the preset constraint shows up in the docs,
# not just as a free-form string (#3549 / BE-NEW-91).


class ToggleEnhancementRequest(BaseModel):
    enabled: bool


class SetPresetRequest(BaseModel):
    # Lowercase before validation; Literal still enforces canonical form.
    preset: EnhancementPresetLiteral

    @field_validator('preset', mode='before')
    @classmethod
    def lowercase_preset(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower()
        return v


class SetIntensityRequest(BaseModel):
    # Shared constraint (#4600). This used to silently clamp and return 200 with
    # a value the caller never sent, while PUT /api/settings 422'd the same
    # input. Worse, `max(0.0, min(1.0, nan))` is `1.0` — a NaN intensity became
    # MAXIMUM enhancement in the runtime settings dict rather than an error.
    # Both REST surfaces now share one definition, as `preset` already does.
    intensity: EnhancementIntensity


class EnhancementSettings(BaseModel):
    """Current enhancement settings.

    #4424 made ``EnhancementPresetLiteral`` the single source of truth and
    migrated the request side; the response side kept a bare ``str`` until
    #4710. That mattered because the frontend narrows on the same closed union
    (``EnhancementSettingsChangedMessage.data.preset``), so a non-canonical
    value serialized straight through and dropped the enhancement UI out of
    its switch — and OpenAPI advertised a free-form string for a closed enum.
    """
    enabled: bool
    preset: EnhancementPresetLiteral
    # EnhancementIntensity carries the canonical ge=0.0/le=1.0 bound (#4600),
    # which also rejects NaN and ±inf for free.
    intensity: EnhancementIntensity


class EnhancementSettingsResponse(BaseModel):
    """Response for enhancement mutation endpoints."""
    message: str
    settings: EnhancementSettings


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_enhancement_router() used to be a 380-line closure: every handler
# below was nested inside it purely to reach get_enhancement_settings/
# connection_manager/get_player_state_manager/etc. via closure capture, which
# made a handler impossible to import or call without first building the whole
# router. Handlers are now module level; they reach the same dependencies
# through FastAPI Depends() instead.
#
# _EnhancementDeps holds the raw callables/objects the factory receives. It is
# populated exactly once, by create_enhancement_router() itself -- same as the
# old closure, which only ever ran once per process (config/routes.py calls
# the factory a single time at startup; the test `client` fixture imports the
# already-built `main.app` once per process too). This is a deliberate
# simplification, not a new hazard: production never calls
# create_enhancement_router() more than once in the same process. It does NOT
# reproduce the #4361 module-level-`APIRouter()` hazard -- which this file DID
# have until now -- since the router instance itself is built fresh, per call,
# inside the factory below.
#
# A handler's Depends() default is only consulted when FastAPI itself invokes
# it for a real request; a direct unit-test call passes the dependency
# explicitly as a keyword argument and never touches _EnhancementDeps at all
# -- that's the seam #4670 asked for.
#
# The optional dependencies (player state manager, multi-tier buffer,
# repository factory) resolve to None when the factory was not given the
# corresponding callable, so the handlers' original "is it wired up at all?"
# guards become plain truthiness checks on the resolved object.
# ============================================================================

class _EnhancementDeps:
    get_enhancement_settings: Callable[[], dict[str, Any]]
    connection_manager: Any
    get_multi_tier_buffer: Callable[[], Any] | None = None
    get_player_state_manager: Callable[[], Any] | None = None
    get_repository_factory: Callable[[], Any] | None = None


_deps = _EnhancementDeps()


def _get_enhancement_settings() -> dict[str, Any]:
    """The live, shared-by-reference runtime settings dict (#4409).

    Returned as-is, never copied: callers mutate it in place so the change
    propagates to every other holder of the same object.
    """
    return _deps.get_enhancement_settings()


def _get_connection_manager() -> Any:
    return _deps.connection_manager


def _get_player_state_manager() -> Any:
    """Optional dependency: None when the factory got no callable for it."""
    if _deps.get_player_state_manager is None:
        return None
    return _deps.get_player_state_manager()


def _get_multi_tier_buffer() -> Any:
    """Optional dependency: None when the factory got no callable for it."""
    if _deps.get_multi_tier_buffer is None:
        return None
    return _deps.get_multi_tier_buffer()


def _get_repository_factory() -> Any:
    """Optional dependency: None when the factory got no callable for it."""
    if _deps.get_repository_factory is None:
        return None
    return _deps.get_repository_factory()


async def _preprocess_upcoming_chunks(track_id: int, filepath: str, current_time: float, preset: str, intensity: float) -> None:
    """
    Background task to pre-process upcoming chunks when enhancement is enabled mid-playback.
    This prevents audio stopping while waiting for on-demand processing.

    Args:
        track_id: Track database ID
        filepath: Path to audio file
        current_time: Current playback position in seconds
        preset: Enhancement preset name
        intensity: Enhancement intensity (0.0-1.0)
    """
    try:
        # Import here to avoid circular dependencies
        from auralis.io.unified_loader import get_audio_info
        from core.chunked_processor import ChunkedAudioProcessor

        # Get audio duration to avoid processing non-existent chunks.
        # #5052: bare sf.info()/soundfile.SoundFile() cannot open
        # .m4a/.aac/.wma — get_audio_info() routes FFmpeg-only formats
        # through ffprobe instead (same fix pattern as #4497's
        # _load_metadata()). It doesn't raise on a probe failure; it
        # sets info_dict['error'] and omits 'duration_seconds', so check
        # explicitly rather than trusting the key is present.
        audio_info = await asyncio.to_thread(get_audio_info, filepath)
        total_duration = audio_info.get('duration_seconds')
        if not total_duration:
            raise ValueError(
                f"Could not determine duration for {filepath}: "
                f"{audio_info.get('error', 'no duration_seconds in probe result')}"
            )
        # Match ChunkedAudioProcessor's content-chunk count so we don't
        # pre-process a spurious trailing chunk (#4124).
        total_chunks = content_chunk_count(total_duration)

        # Calculate current chunk and next 3 chunks to pre-process, via
        # chunk_for_position() (#4557/#4791) — the mapping onto the chunk
        # that actually EMITS current_time, not a naive core-timeline
        # division by CHUNK_INTERVAL, which is off by one for roughly
        # the first half of every emitted chunk window and was skipping
        # the immediately-next chunk (the one whose absence causes the
        # stall this pre-fetch exists to prevent).
        current_chunk_idx = chunk_for_position(current_time, total_chunks)[0]
        chunks_to_process = [current_chunk_idx + i for i in range(1, 4)]  # Next 3 chunks

        logger.info(f"🎯 Pre-processing chunks {chunks_to_process} for track {track_id} (current chunk: {current_chunk_idx})")

        # Create processor (may perform file I/O — run in thread).
        # #5052: for any format sf.info() can't open, ChunkedAudioProcessor's
        # SeekableSource decodes the whole track to a temp-dir WAV that only
        # processor.close() releases — every other construction site in the
        # backend closes explicitly, this one must too (try/finally below).
        processor = await asyncio.to_thread(
            ChunkedAudioProcessor,
            track_id=track_id,
            filepath=filepath,
            preset=preset,
            intensity=intensity,
            chunk_cache={},
        )
        try:
            # Process each chunk
            processed_count = 0
            for chunk_idx in chunks_to_process:
                if chunk_idx >= total_chunks:
                    break  # Don't process chunks beyond the track

                try:
                    # Process chunk (this will cache the WAV file).
                    # get_wav_chunk_path does CPU-bound audio processing; run in a
                    # thread pool to avoid blocking the event loop (fixes #2330).
                    wav_chunk_path = await asyncio.to_thread(processor.get_wav_chunk_path, chunk_idx)

                    if os.path.exists(wav_chunk_path):
                        processed_count += 1
                        logger.info(f"✅ Pre-processed chunk {chunk_idx} ({processed_count}/{len(chunks_to_process)})")
                    else:
                        logger.warning(f"⚠️ Pre-processing failed for chunk {chunk_idx}: output file not found")

                except Exception as e:
                    logger.error(f"❌ Pre-processing failed for chunk {chunk_idx}: {e}")
                    continue

            logger.info(f"🎯 Pre-processing complete: {processed_count} chunks ready")
        finally:
            await asyncio.to_thread(processor.close)

    except Exception as e:
        logger.error(f"❌ Background chunk pre-processing failed: {e}")


def _maybe_prewarm_upcoming_chunks(
    enhancement_settings: dict[str, Any],
    player_state_manager: Any,
) -> None:
    """Launch background pre-processing of the next few chunks at the
    current preset/intensity, mirroring the toggle-ON pre-warm (#2296).

    Only fires when a track is actively playing — otherwise there is no
    "upcoming" position to pre-process from, same guard toggle_enhancement
    already used. Shared by toggle_enhancement/set_enhancement_preset/
    set_enhancement_intensity (#4425) so a preset or intensity change mid-
    playback gets the same "no audible on-demand gap" treatment the
    enable-toggle path already had.
    """
    if not player_state_manager:
        return
    state = player_state_manager.get_state()
    if not (state.current_track and state.state.value == "playing"):
        return
    spawn_background_task(
        _preprocess_upcoming_chunks(
            track_id=state.current_track.id,
            filepath=state.current_track.filepath,
            current_time=state.current_time,
            preset=enhancement_settings.get("preset", "adaptive"),
            intensity=enhancement_settings.get("intensity", 1.0),
        ),
        name="enhancement._preprocess_upcoming_chunks",
    )
    logger.info(
        f"🎯 Launched background pre-processing for track {state.current_track.id} "
        f"at {state.current_time:.1f}s"
    )


@with_error_handling("toggle enhancement")
async def toggle_enhancement(
    body: ToggleEnhancementRequest,
    enhancement_settings: dict[str, Any] = Depends(_get_enhancement_settings),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
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
    enabled = body.enabled
    enhancement_settings["enabled"] = enabled

    # If enabling enhancement mid-playback, pre-process upcoming chunks in
    # background (#2296) so the client doesn't hit an on-demand processing gap.
    if enabled:
        _maybe_prewarm_upcoming_chunks(enhancement_settings, player_state_manager)

    # Broadcast to all clients
    await connection_manager.broadcast({
        "type": "enhancement_settings_changed",
        "data": {
            "enabled": enabled,
            "preset": enhancement_settings["preset"],
            "intensity": enhancement_settings["intensity"]
        }
    })

    logger.info(f"Enhancement {'enabled' if enabled else 'disabled'}")
    return {
        "message": f"Enhancement {'enabled' if enabled else 'disabled'}",
        "settings": enhancement_settings
    }


@with_error_handling("change preset")
async def set_enhancement_preset(
    body: SetPresetRequest,
    enhancement_settings: dict[str, Any] = Depends(_get_enhancement_settings),
    buffer_manager: Any = Depends(_get_multi_tier_buffer),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """
    Change the enhancement preset.

    Args:
        preset: Preset name (adaptive, gentle, warm, bright, punchy)

    Returns:
        dict: Status message and current settings

    Raises:
        HTTPException: If preset is invalid or change fails
    """
    preset = body.preset  # already validated and lowercased by SetPresetRequest
    old_preset = enhancement_settings.get("preset")
    enhancement_settings["preset"] = preset

    # Update multi-tier buffer manager for branch prediction learning
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

    # Broadcast to all clients
    await connection_manager.broadcast({
        "type": "enhancement_settings_changed",
        "data": {
            "preset": preset,
            "enabled": enhancement_settings["enabled"],
            "intensity": enhancement_settings["intensity"]
        }
    })

    logger.info(f"Enhancement preset changed to: {preset}")
    return {
        "message": f"Preset changed to {preset}",
        "settings": enhancement_settings
    }


@with_error_handling("set intensity")
async def set_enhancement_intensity(
    body: SetIntensityRequest,
    enhancement_settings: dict[str, Any] = Depends(_get_enhancement_settings),
    buffer_manager: Any = Depends(_get_multi_tier_buffer),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
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

    preset = enhancement_settings.get("preset", "adaptive")

    # Notify multi-tier buffer manager so pre-buffered chunks at the old
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

    # Broadcast to all clients
    await connection_manager.broadcast({
        "type": "enhancement_settings_changed",
        "data": {
            "intensity": intensity,
            "enabled": enhancement_settings["enabled"],
            "preset": enhancement_settings["preset"]
        }
    })

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


@with_error_handling("generate mastering recommendation")
async def get_mastering_recommendation(
    track_id: int,
    confidence_threshold: float = Query(
        0.4,
        ge=0.0,
        le=1.0,
        description="Threshold for switching from single to blended recommendations",
    ),
    repos: Any = Depends(_get_repository_factory),
) -> dict[str, Any]:
    """
    Get weighted mastering profile recommendation for a track (Priority 4).

    Analyzes the track's audio characteristics and returns single or blended
    profile recommendations based on confidence thresholds.

    The filepath is resolved from the database by track_id to prevent
    mismatched track/file analysis (fixes #2731).

    Args:
        track_id: Track database ID
        confidence_threshold: Threshold for switching from single to blended recommendations (0.0-1.0)

    Returns:
        dict: MasteringRecommendation serialized to JSON with weighted_profiles if hybrid

    Raises:
        HTTPException: 404 if track not found
        HTTPException: 503 if repository unavailable
        HTTPException: 500 if analysis fails
    """
    # Resolve filepath from DB by track_id (fixes #2731)
    if repos is None:
        raise HTTPException(status_code=503, detail="Repository not available")

    track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)
    if not track:
        raise NotFoundError("Track", track_id)

    filepath = track.filepath
    if not filepath:
        raise HTTPException(status_code=400, detail=f"Track {track_id} has no filepath")

    # Return cached result if still valid — avoids re-running full audio
    # analysis (~1-5 s CPU) on repeated calls for the same track (#3865).
    _cache_key = (track_id, confidence_threshold)
    _now = time.monotonic()
    _cached = _recommendation_cache.get(_cache_key)
    if _cached is not None:
        _expiry, _cached_result = _cached
        if _now < _expiry:
            # Keep hot entries away from the FIFO eviction end (#4657).
            _recommendation_cache.move_to_end(_cache_key)
            logger.debug(f"Returning cached mastering recommendation for track {track_id}")
            return _cached_result
        # Expired: drop it now rather than leaving it resident until the
        # next insert happens to purge (#4657).
        del _recommendation_cache[_cache_key]

    try:
        from core.chunked_processor import ChunkedAudioProcessor

        # Run CPU-bound processor off the event loop (#2301)
        _fp = str(filepath)
        _tid = track_id
        _ct = confidence_threshold

        def _run_recommendation() -> dict | None:
            proc = ChunkedAudioProcessor(
                track_id=_tid,
                filepath=_fp,
                preset="adaptive",  # Default for analysis-only mode
                intensity=1.0,
                chunk_cache={}
            )
            rec = proc.get_mastering_recommendation(confidence_threshold=_ct)
            # Use to_response (not to_dict) so the payload carries track_id +
            # is_hybrid and honors MasteringRecommendationResponse (#3840).
            return rec.to_response(_tid) if rec is not None else None

        result = await asyncio.to_thread(_run_recommendation)

        if result is None:
            raise HTTPException(status_code=500, detail="Failed to analyze audio file")

        result_dict = result if isinstance(result, dict) else {}
        _store_recommendation(_cache_key, _now + _RECOMMENDATION_TTL_S, result_dict)
        return result_dict

    except HTTPException:
        raise


# Moved to routers/processing_api.py (#5073): GET /api/processing/parameters
# was owned by this router but registered unconditionally, unlike its 8
# HAS_PROCESSING-gated siblings under the same /api/processing prefix. It
# now lives on create_processing_router() so ownership, gating, and the
# OpenAPI "audio-processing" tag are consistent with the rest of that
# namespace.


def create_enhancement_router(
    get_enhancement_settings: Callable[[], dict[str, Any]],
    connection_manager: Any,
    get_multi_tier_buffer: Callable[[], Any] | None = None,
    get_player_state_manager: Callable[[], Any] | None = None,
    get_processing_engine: Callable[[], Any] | None = None,
    get_repository_factory: Callable[[], Any] | None = None,
) -> APIRouter:
    """
    Factory function to create enhancement router with dependencies.

    Args:
        get_enhancement_settings: Callable that returns enhancement settings dict
        connection_manager: WebSocket connection manager for broadcasts
        get_player_state_manager: Optional callable that returns PlayerStateManager
        get_processing_engine: Optional callable that returns ProcessingEngine
        get_repository_factory: Optional callable that returns RepositoryFactory

    Returns:
        APIRouter: Configured router instance
    """
    # get_processing_engine is accepted for call-site compatibility with
    # config/routes.py but is not used by any handler above -- pre-existing
    # (its only consumer, GET /api/processing/parameters, moved to
    # routers/processing_api.py in #5073), unrelated to #4670.
    _deps.get_enhancement_settings = get_enhancement_settings
    _deps.connection_manager = connection_manager
    _deps.get_multi_tier_buffer = get_multi_tier_buffer
    _deps.get_player_state_manager = get_player_state_manager
    _deps.get_repository_factory = get_repository_factory

    router = APIRouter(tags=["enhancement"])

    router.add_api_route("/api/player/enhancement/toggle", toggle_enhancement, methods=["POST"], response_model=EnhancementSettingsResponse)
    router.add_api_route("/api/player/enhancement/preset", set_enhancement_preset, methods=["POST"], response_model=EnhancementSettingsResponse)
    router.add_api_route("/api/player/enhancement/intensity", set_enhancement_intensity, methods=["POST"], response_model=EnhancementSettingsResponse)
    router.add_api_route("/api/player/enhancement/status", get_enhancement_status, methods=["GET"], response_model=EnhancementSettings)
    router.add_api_route(
        "/api/player/mastering/recommendation/{track_id}",
        get_mastering_recommendation,
        methods=["GET"],
        response_model=MasteringRecommendationResponse,
    )

    return router
