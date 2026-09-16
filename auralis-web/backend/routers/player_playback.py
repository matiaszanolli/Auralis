"""
Player Playback Endpoints

Playback control (status, load, seek, volume) and navigation (next,
previous) under /api/player. Split out of routers/player.py (#5472), whose
create_player_router() registers them.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any

from fastapi import BackgroundTasks, Depends, HTTPException

from services import NavigationService, PlaybackService, RecommendationService
from websocket.outbound_messages import broadcast_typed

from .dependencies import with_error_handling
from .errors import (
    AudioPlayerUnavailableError,
    LibraryManagerUnavailableError,
    NotFoundError,
    raise_for_service_error,
)
from .player_deps import (
    _get_audio_player,
    _get_connection_manager,
    _get_library_database,
    _get_navigation_service,
    _get_playback_service,
    _get_player_state_manager,
    _get_recommendation_service,
)
from .player_models import LoadTrackRequest, SeekRequest, SetVolumeRequest

logger = logging.getLogger(__name__)


# ============================================================================
# PLAYBACK ENDPOINTS
# ============================================================================

@with_error_handling("get player status")
async def get_player_status(
    service: PlaybackService = Depends(_get_playback_service),
) -> dict[str, Any]:
    """
    Get current player status (single source of truth).

    Returns:
        dict: Player state with track info, playback status, queue

    Raises:
        HTTPException: If player not available or query fails
    """
    try:
        return await service.get_status()
    except ValueError as e:
        raise_for_service_error(e, "get player status")


@with_error_handling("load track")
async def load_track(
    request: LoadTrackRequest,
    background_tasks: BackgroundTasks,
    audio_player: Any = Depends(_get_audio_player),
    library_database: Any = Depends(_get_library_database),
    connection_manager: Any = Depends(_get_connection_manager),
    recommendation_service: RecommendationService = Depends(_get_recommendation_service),
) -> dict[str, Any]:
    """
    Load a track into the player (database-backed, prevents path traversal).

    Also generates and broadcasts mastering profile recommendation (Priority 4) in background.

    Args:
        request: LoadTrackRequest with track_id (required for security - validates file path)
        background_tasks: FastAPI background tasks

    Returns:
        dict: Success message

    Raises:
        HTTPException: If track not found, audio player not available, or load fails
    """
    if not audio_player:
        raise AudioPlayerUnavailableError()

    # Security: Query track from database to validate file path (offloaded — sync DB call)
    # This deref sits outside the try: below, so a None manager escaped as an
    # unhandled AttributeError rather than an actionable 503 (#4656).
    if library_database is None:
        raise LibraryManagerUnavailableError()

    track = await asyncio.to_thread(library_database.tracks.get_by_id, request.track_id)
    if not track:
        raise NotFoundError("Track", detail=f"Track {request.track_id} not found in library")

    # Add to queue with track info dict (using validated filepath from database).
    # The queue entry is what the gapless engine reads on next_track; loading
    # the audio file itself is done by load_track_from_library() below
    # (fixes #3491 — the previous `audio_player.load_current_track()` call
    # invoked a method that does not exist on AudioPlayer, so the
    # hasattr() check always returned False and the endpoint reported success
    # while never actually loading the file).
    track_info = {
        'filepath': track.filepath,  # Security: Use validated path from database
        'id': track.id,
    }
    # Offload — add_to_queue() may synchronously load the file (SoundFile
    # open, 50-500ms) when the player has nothing loaded yet, e.g. the
    # very first track played this session (fixes #3815 / BE-PF-1).
    await asyncio.to_thread(audio_player.add_to_queue, track_info)
    success = await asyncio.to_thread(
        audio_player.load_track_from_library, request.track_id
    )

    if success:
        # Broadcast to all connected clients — omit filepath to avoid leaking
        # the server filesystem layout to browser clients (fixes #2479).
        await broadcast_typed(
            connection_manager,
            "track_loaded",
            {"track_id": track.id},
        )

        # Generate mastering recommendation in background (Priority 4)
        background_tasks.add_task(
            recommendation_service.generate_and_broadcast_recommendation,
            track_id=track.id,
            track_path=track.filepath
        )
        logger.info(f"🎯 Scheduled mastering recommendation generation for track {track.id}")

        return {"message": "Track loaded successfully", "track_id": track.id}
    else:
        raise HTTPException(status_code=400, detail="Failed to load track")


@with_error_handling("seek")
async def seek_position(
    request: SeekRequest,
    player_state_manager: Any = Depends(_get_player_state_manager),
    service: PlaybackService = Depends(_get_playback_service),
) -> dict[str, Any]:
    """
    Seek to position in seconds.

    Args:
        request: SeekRequest with position in seconds (must be finite and non-negative)

    Returns:
        dict: Success message and new position

    Raises:
        HTTPException 422: If position is negative, NaN, or Infinity (Pydantic validation)
        HTTPException 400: If position exceeds current track duration
        HTTPException 503: If audio player is unavailable
    """
    position = request.position

    # Validate against current track duration when a track is loaded
    if player_state_manager:
        state = player_state_manager.get_state()
        if state.duration > 0 and position > state.duration:
            raise HTTPException(
                status_code=400,
                detail=f"Position {position:.1f}s exceeds track duration {state.duration:.1f}s"
            )

    try:
        result = await service.seek(position)
        return result
    except ValueError as e:
        raise_for_service_error(e, "seek")


@with_error_handling("set volume")
async def set_volume(
    body: SetVolumeRequest,
    service: PlaybackService = Depends(_get_playback_service),
) -> dict[str, Any]:
    """
    Set playback volume.

    Args:
        body: JSON body with volume level (0-100, converted to 0.0-1.0 internally)

    Returns:
        dict: Success message and new volume

    Raises:
        HTTPException: If player service unavailable or volume out of range
    """
    try:
        # Convert 0-100 to 0.0-1.0 for service layer (clamping already done by model)
        normalized_volume = body.volume / 100.0
        result = await service.set_volume(normalized_volume)
        # #3204 converted the response back to a 0-100 scale by substituting
        # the caller's raw body.volume — but service.set_volume() already
        # returns a rounded 0-100 int (the same value broadcast in the paired
        # volume_changed WS message), so that substitution let a fractional
        # body.volume disagree with the broadcast by up to 0.5 (#5050).
        # result["volume"] is already on the right scale; nothing to convert.
        return result
    except ValueError as e:
        # #5268: set_volume() used to raise a plain ValueError for BOTH "audio
        # player not available" (a transient server-state condition, should be
        # 503 like the seek route's analogous case above) and "volume out of
        # range" (a genuine bad-request, 400) — this route couldn't tell them
        # apart. It now raises ServiceUnavailable for the former, which
        # raise_for_service_error maps to 503; any other ValueError still
        # defaults to 400, preserving today's behavior for the range check
        # (unreachable via this route in practice, since SetVolumeRequest
        # clamps rather than rejects, but the service validates it
        # defensively for any future caller that doesn't).
        raise_for_service_error(e, "set volume")


# ============================================================================
# NAVIGATION ENDPOINTS
# ============================================================================

@with_error_handling("skip track")
async def next_track(service: NavigationService = Depends(_get_navigation_service)) -> dict[str, Any]:
    """Skip to next track."""
    try:
        return await service.next_track()
    except ValueError as e:
        raise_for_service_error(e, "skip to next track")


@with_error_handling("skip track")
async def previous_track(service: NavigationService = Depends(_get_navigation_service)) -> dict[str, Any]:
    """Skip to previous track."""
    try:
        return await service.previous_track()
    except ValueError as e:
        raise_for_service_error(e, "skip to previous track")
