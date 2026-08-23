"""
Player Router

Handles audio playback control and queue management via FastAPI endpoints.
Delegates business logic to service layer (PlaybackService, QueueService,
RecommendationService, NavigationService).

Note: Audio streaming is now handled exclusively via WebSocket using the WebSocket controller.
      No REST streaming endpoints remain (consolidated to unified WebSocket architecture).

Endpoints:
- GET /api/player/status - Get current player status
- POST /api/player/load - Load track
- POST /api/player/seek - Seek to position
- POST /api/player/volume - Set volume
- GET /api/player/queue - Get queue
- POST /api/player/queue - Set queue
- POST /api/player/queue/add-track - Add track to queue (with position support)
- DELETE /api/player/queue/{index} - Remove from queue
- PUT /api/player/queue/reorder - Reorder queue
- POST /api/player/queue/clear - Clear queue
- POST /api/player/queue/shuffle - Shuffle queue
- POST /api/player/next - Next track
- POST /api/player/previous - Previous track

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import math
from typing import Annotated, Any, Literal, cast
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query

from .dependencies import with_error_handling
from .errors import NotFoundError, raise_for_service_error
from pydantic import BaseModel, ConfigDict, Field, field_validator
from player_state import PlayerState, TrackInfo
from schemas import QueueIndex, QueueIndexList, TrackId, TrackIdList
from services import (
    NavigationService,
    PlaybackService,
    QueueService,
    RecommendationService,
    ServiceUnavailable,
)

logger = logging.getLogger(__name__)


class SetQueueRequest(BaseModel):
    """Request model for setting the playback queue"""
    tracks: TrackIdList
    start_index: QueueIndex = 0


class ReorderQueueRequest(BaseModel):
    """Request model for reordering the queue.

    ``new_order`` is a permutation of the queue's current *indices*, not track
    ids. Bounds are per-element and on length; whether the list is actually a
    permutation of the live queue is a runtime question QueueService answers,
    not one a body model can.
    """
    new_order: QueueIndexList


class MoveQueueTrackRequest(BaseModel):
    """Request model for moving a track within the queue (drag-and-drop)"""
    from_index: QueueIndex
    to_index: QueueIndex


class AddTrackToQueueRequest(BaseModel):
    """Request model for adding a track to queue with position"""
    track_id: TrackId
    position: QueueIndex | None = None  # None = append to end


class LoadTrackRequest(BaseModel):
    """Request model for loading a track"""
    track_id: TrackId


class SeekRequest(BaseModel):
    """Request model for seek operation with input validation.

    Deliberately has no upper bound (#4681). The only meaningful ceiling is the
    loaded track's duration, which a body model cannot see; the route applies
    that check when a track is loaded, and
    `tests/backend/test_player_api_comprehensive.py::test_seek_overflow_protection`
    pins the no-track-loaded case to a pass-through 200. A fixed numeric cap
    here would be arbitrary and would break that documented contract.
    """
    position: float

    @field_validator('position')
    @classmethod
    def validate_position(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Position must be a finite number")
        if v < 0:
            raise ValueError("Position must be non-negative")
        return v


class SetVolumeRequest(BaseModel):
    """Request model for volume control (0–100)."""
    # #3896 proposed replacing the validator with Field(ge=0, le=100) so the
    # bounds appear in OpenAPI. Deliberately not done: that converts a forgiving
    # clamp into a 422, and tests/integration/test_phase4_player_workflow.py::
    # test_volume_out_of_range sends 150 and -50 and asserts a SUCCESSFUL
    # response with a clamped value. Clamping is the intended contract, so the
    # range is documented instead of enforced.
    volume: float = Field(
        description="Playback volume on a 0-100 scale. Values outside the "
                    "range are clamped, not rejected.",
    )

    @field_validator('volume')
    @classmethod
    def clamp_volume(cls, v: float) -> float:
        return max(0.0, min(100.0, v))


class ShuffleRequest(BaseModel):
    """Request model for shuffle toggle."""
    enabled: bool = True


class RepeatModeRequest(BaseModel):
    """Request model for setting repeat mode."""
    mode: Literal["off", "all", "one"]


class QueueHistoryStateSnapshot(BaseModel):
    """Queue state snapshot carried by a history entry (#3805)."""
    track_ids: TrackIdList
    current_index: QueueIndex = 0
    is_shuffled: bool = False
    repeat_mode: Literal["off", "all", "one"] = "off"


class RecordQueueHistoryRequest(BaseModel):
    """Request model for POST /api/player/queue/history (#3805)."""
    operation: Literal["set", "add", "remove", "reorder", "shuffle", "clear"]
    state_snapshot: QueueHistoryStateSnapshot
    operation_metadata: dict[str, Any] = {}


# ============================================================================
# RESPONSE MODELS (#2751 — OpenAPI schema documentation)
# ============================================================================

class MessageResponse(BaseModel):
    """Generic response with a message."""
    message: str


class LoadTrackResponse(BaseModel):
    """Response for POST /api/player/load."""
    message: str
    track_id: int


class SeekResponse(BaseModel):
    """Response for POST /api/player/seek."""
    message: str
    position: float


class VolumeResponse(BaseModel):
    """Response for POST /api/player/volume."""
    message: str
    volume: float


class QueueInfoResponse(BaseModel):
    """Response for GET /api/player/queue."""
    # tracks/current_track are canonical TrackInfo (#4374): queue_service
    # enriches the engine queue's filepath-only entries into full TrackInfo
    # before returning, so the schema is real rather than `Any`.
    tracks: list[TrackInfo]
    current_index: int
    track_count: int | None = None
    current_track: TrackInfo | None = None
    has_next: bool | None = None
    has_previous: bool | None = None
    shuffle_enabled: bool | None = None
    # repeat_mode, not the engine's repeat_enabled bool (#3896). The engine
    # queue only knows "repeat the queue: yes/no", but the canonical
    # PlayerState.repeat_mode is three-valued, so a bool here silently collapsed
    # "all" and "one" into the same response. That made this endpoint unable to
    # populate the frontend's Queue.repeatMode, forcing callers to
    # GET /api/player/status instead and defeating the queue endpoint.
    # Matches PlayerState.repeat_mode above.
    repeat_mode: Literal["off", "all", "one"] | None = None

    model_config = ConfigDict(extra='allow')


class SetQueueResponse(BaseModel):
    """Response for POST /api/player/queue."""
    message: str
    track_count: int
    start_index: int


class QueueSizeResponse(BaseModel):
    """Response for queue operations that return message + queue_size."""
    message: str
    queue_size: int


class AddTrackToQueueResponse(BaseModel):
    """Response for POST /api/player/queue/add-track."""
    message: str
    track_id: int
    position: int | None
    queue_size: int


class RemoveFromQueueResponse(BaseModel):
    """Response for DELETE /api/player/queue/{index}."""
    message: str
    index: int
    queue_size: int


class MoveQueueTrackResponse(BaseModel):
    """Response for PUT /api/player/queue/move."""
    message: str
    from_index: int
    to_index: int
    queue_size: int


class QueueHistoryEntryResponse(BaseModel):
    """Single queue history entry (#3805)."""
    id: int
    operation: str
    state_snapshot: dict[str, Any]
    operation_metadata: dict[str, Any]
    created_at: str | None = None

    model_config = ConfigDict(extra='allow')


class QueueHistoryListResponse(BaseModel):
    """Response for GET /api/player/queue/history (#3805)."""
    history: list[QueueHistoryEntryResponse]
    count: int


class UndoQueueResponse(BaseModel):
    """Response for POST /api/player/queue/undo (#3805)."""
    message: str
    queue_state: dict[str, Any]


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_player_router() used to be a 515-line closure: every handler below
# was nested inside it purely to reach get_library_manager/get_audio_player/
# etc. via closure capture, which made a handler impossible to import or
# call without first building the whole router. Handlers are now module
# level; they reach the same callables through FastAPI Depends() instead.
#
# _PlayerDeps holds the raw callables/objects the factory receives. It is
# populated exactly once, by create_player_router() itself -- same as the
# old closure, which only ever ran once per process (config/routes.py calls
# the factory a single time at startup; the test `client` fixture imports
# the already-built `main.app` once per process too). This is a deliberate
# simplification, not a new hazard: nothing in this codebase calls
# create_player_router() more than once in the same process. It does NOT
# reproduce the #4361 module-level-`APIRouter()` hazard, since the router
# instance itself is still built fresh, per call, inside the factory below.
#
# A handler's Depends() default is only consulted when FastAPI itself
# invokes it for a real request; a direct unit-test call passes the
# service/dependency explicitly as a keyword argument and never touches
# _PlayerDeps at all -- that's the seam #4670 asked for.
# ============================================================================

class _PlayerDeps:
    get_library_manager: Callable[[], Any]
    get_audio_player: Callable[[], Any]
    get_player_state_manager: Callable[[], Any]
    connection_manager: Any
    create_track_info_fn: Callable[[Any], Any]


_deps = _PlayerDeps()


def _get_audio_player() -> Any:
    return _deps.get_audio_player()


def _get_library_manager() -> Any:
    return _deps.get_library_manager()


def _get_player_state_manager() -> Any:
    return _deps.get_player_state_manager()


def _get_connection_manager() -> Any:
    return _deps.connection_manager


def _get_playback_service(
    audio_player: Any = Depends(_get_audio_player),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
) -> PlaybackService:
    """Lazy service initialization"""
    return PlaybackService(
        audio_player=audio_player,
        player_state_manager=player_state_manager,
        connection_manager=connection_manager,
    )


def _get_queue_service(
    audio_player: Any = Depends(_get_audio_player),
    player_state_manager: Any = Depends(_get_player_state_manager),
    library_manager: Any = Depends(_get_library_manager),
    connection_manager: Any = Depends(_get_connection_manager),
) -> QueueService:
    """Lazy service initialization"""
    return QueueService(
        audio_player=audio_player,
        player_state_manager=player_state_manager,
        library_manager=library_manager,
        connection_manager=connection_manager,
        create_track_info_fn=_deps.create_track_info_fn,
    )


def _get_recommendation_service(
    connection_manager: Any = Depends(_get_connection_manager),
) -> RecommendationService:
    """Lazy service initialization"""
    return RecommendationService(connection_manager=connection_manager)


def _get_navigation_service(
    audio_player: Any = Depends(_get_audio_player),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
) -> NavigationService:
    """Lazy service initialization"""
    return NavigationService(
        audio_player=audio_player,
        player_state_manager=player_state_manager,
        connection_manager=connection_manager,
        create_track_info_fn=_deps.create_track_info_fn,
    )


def _get_queue_history_repo(library_manager: Any = Depends(_get_library_manager)) -> Any:
    """Lazy repository initialization (#3805).

    Constructed directly from the library manager's session factory
    rather than via RepositoryFactory — this router only receives
    get_library_manager, not get_repository_factory. QueueHistoryRepository
    is cheap to construct (BaseRepository just holds the session factory;
    no per-instance caching needed for occasional undo/history calls).
    """
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")
    from auralis.library.repositories.queue_history_repository import (
        QueueHistoryRepository,
    )
    return QueueHistoryRepository(library_manager.SessionLocal)


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
        raise HTTPException(status_code=503, detail=str(e))


@with_error_handling("load track")
async def load_track(
    request: LoadTrackRequest,
    background_tasks: BackgroundTasks,
    audio_player: Any = Depends(_get_audio_player),
    library_manager: Any = Depends(_get_library_manager),
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
        raise HTTPException(status_code=503, detail="Audio player not available")

    # Security: Query track from database to validate file path (offloaded — sync DB call)
    # This deref sits outside the try: below, so a None manager escaped as an
    # unhandled AttributeError rather than an actionable 503 (#4656).
    if library_manager is None:
        raise HTTPException(status_code=503, detail="Library manager not available")

    track = await asyncio.to_thread(library_manager.tracks.get_by_id, request.track_id)
    if not track:
        raise NotFoundError("Track", detail=f"Track {request.track_id} not found in library")

    try:
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
            await connection_manager.broadcast({
                "type": "track_loaded",
                "data": {"track_id": track.id}
            })

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

    except HTTPException:
        raise


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
        raise HTTPException(status_code=503, detail=str(e))


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
        # Convert back to 0-100 for API response (fixes #3204)
        result["volume"] = body.volume
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# QUEUE ENDPOINTS
# ============================================================================

@with_error_handling("get queue")
async def get_queue(service: QueueService = Depends(_get_queue_service)) -> dict[str, Any]:
    """Get current playback queue."""
    try:
        return await service.get_queue_info()
    except ValueError as e:
        raise_for_service_error(e, "get queue")


@with_error_handling("set queue")
async def set_queue(
    request: SetQueueRequest,
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Set the playback queue (updates single source of truth)."""
    try:
        return await service.set_queue(request.tracks, request.start_index)
    except ValueError as e:
        raise_for_service_error(e, "set queue")


# ============================================================================
# QUEUE HISTORY / UNDO ENDPOINTS (#3805)
#
# NOTE: Registered BEFORE the `/api/player/queue/{index}` DELETE route
# below. FastAPI/Starlette match routes in registration order, not by
# literal-vs-parameterized specificity — if `/api/player/queue/history`
# were registered after `/api/player/queue/{index}`, a DELETE to
# `.../history` would match `{index}` first and fail int coercion (422)
# instead of ever reaching this route.
# ============================================================================

@with_error_handling("get queue history")
async def get_queue_history(
    limit: int = Query(20, ge=1, le=100),
    repo: Any = Depends(_get_queue_history_repo),
) -> dict[str, Any]:
    """Get recent queue-operation history entries (newest first)."""
    try:
        entries = await asyncio.to_thread(repo.get_history, limit)
        history = [entry.to_dict() for entry in entries]
        return {"history": history, "count": len(history)}
    except HTTPException:
        raise


@with_error_handling("record queue history")
async def record_queue_history(
    request: RecordQueueHistoryRequest,
    repo: Any = Depends(_get_queue_history_repo),
) -> dict[str, Any]:
    """Record a queue-state snapshot to history, for later undo."""
    try:
        entry = await asyncio.to_thread(
            repo.push_to_history,
            request.operation,
            request.state_snapshot.model_dump(),
            request.operation_metadata,
        )
        return cast(dict[str, Any], entry.to_dict())
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@with_error_handling("undo queue operation")
async def undo_queue_operation(
    repo: Any = Depends(_get_queue_history_repo),
    queue_service: QueueService = Depends(_get_queue_service),
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """Undo the last recorded queue operation.

    Restores both the persisted QueueState row and the live queue
    (track order + position via QueueService.set_queue, repeat/shuffle
    flags via PlayerStateManager) — restoring only the DB snapshot would
    make "undo" silently do nothing from the user's perspective (#3805).
    """
    try:
        restored = await asyncio.to_thread(repo.undo)
        if restored is None:
            raise NotFoundError("History", detail="No history available to undo")

        restored_dict = restored.to_dict()

        try:
            await queue_service.set_queue(
                restored_dict['track_ids'], start_index=restored_dict['current_index']
            )
        except ValueError as e:
            # Audio player / state manager not available — the DB state
            # was still restored; degrade gracefully rather than failing
            # the whole undo over a live-sync step.
            logger.warning(f"Queue history restored in DB but live queue sync skipped: {e}")

        if player_state_manager:
            await player_state_manager.update_state(
                repeat_mode=restored_dict['repeat_mode'],
                shuffle_enabled=restored_dict['is_shuffled'],
            )

        # Canonical queue event is `queue_changed` (the #3492 rename that
        # this undo straggler missed); `queue_updated` had no FE subscriber
        # so the dedicated broadcast was silently dropped (#4420).
        await connection_manager.broadcast({
            "type": "queue_changed",
            "data": {
                "action": "undo",
                "current_index": restored_dict['current_index'],
                "queue_size": len(restored_dict['track_ids']),
            },
        })

        return {"message": "Queue operation undone", "queue_state": restored_dict}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@with_error_handling("clear queue history")
async def clear_queue_history(repo: Any = Depends(_get_queue_history_repo)) -> dict[str, Any]:
    """Clear all queue history entries."""
    try:
        await asyncio.to_thread(repo.clear_history)
        return {"message": "Queue history cleared"}
    except HTTPException:
        raise


@with_error_handling("remove from queue")
async def remove_from_queue(
    index: Annotated[int, Path(ge=0)],
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Remove track from queue at specified index."""
    try:
        return await service.remove_track_from_queue(index)
    except ValueError as e:
        raise_for_service_error(e, "remove from queue")


@with_error_handling("reorder queue")
async def reorder_queue(
    request: ReorderQueueRequest,
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Reorder the playback queue."""
    try:
        return await service.reorder_queue(request.new_order)
    except ValueError as e:
        raise_for_service_error(e, "reorder queue")


@with_error_handling("clear queue")
async def clear_queue(service: QueueService = Depends(_get_queue_service)) -> dict[str, Any]:
    """Clear the entire playback queue."""
    try:
        return await service.clear_queue()
    except ValueError as e:
        raise_for_service_error(e, "clear queue")


@with_error_handling("add track to queue")
async def add_track_to_queue(
    request: AddTrackToQueueRequest,
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Add a track to queue at specific position (for drag-and-drop)."""
    try:
        return await service.add_track_to_queue(request.track_id, request.position)
    except ValueError as e:
        raise_for_service_error(e, "add track to queue")


@with_error_handling("move track")
async def move_queue_track(
    request: MoveQueueTrackRequest,
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Move a track within the queue (for drag-and-drop)."""
    try:
        return await service.move_track_in_queue(request.from_index, request.to_index)
    except ValueError as e:
        raise_for_service_error(e, "move track")


@with_error_handling("shuffle queue")
async def shuffle_queue(
    request: ShuffleRequest,
    service: QueueService = Depends(_get_queue_service),
) -> dict[str, Any]:
    """Shuffle or unshuffle the playback queue."""
    try:
        if request.enabled:
            return await service.shuffle_queue()
        else:
            return await service.unshuffle_queue()
    except ValueError as e:
        raise_for_service_error(e, "shuffle queue")


@with_error_handling("set repeat mode")
async def set_repeat_mode(
    request: RepeatModeRequest,
    player_state_manager: Any = Depends(_get_player_state_manager),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """Set the playback repeat mode (off, all, one)."""
    try:
        if not player_state_manager:
            raise ServiceUnavailable("Player state manager not available")

        # Pass through 'off' / 'one' / 'all' — backend now uses the same
        # vocabulary as the frontend Literal (#3501 / BE-NEW-43).
        await player_state_manager.update_state(repeat_mode=request.mode)

        # Broadcast canonical value so WS and REST always agree
        await connection_manager.broadcast({
            "type": "repeat_mode_changed",
            "data": {"repeat_mode": request.mode},
        })

        return {"message": f"Repeat mode set to {request.mode}"}
    except ValueError as e:
        raise_for_service_error(e, "set repeat mode")


# ============================================================================
# NAVIGATION ENDPOINTS
# ============================================================================

@with_error_handling("skip track")
async def next_track(service: NavigationService = Depends(_get_navigation_service)) -> dict[str, Any]:
    """Skip to next track."""
    try:
        return await service.next_track()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


@with_error_handling("skip track")
async def previous_track(service: NavigationService = Depends(_get_navigation_service)) -> dict[str, Any]:
    """Skip to previous track."""
    try:
        return await service.previous_track()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


def create_player_router(
    get_library_manager: Callable[[], Any],
    get_audio_player: Callable[[], Any],
    get_player_state_manager: Callable[[], Any],
    connection_manager: Any,
    chunked_audio_processor_class: type | None,
    create_track_info_fn: Callable[[Any], Any],
    buffer_presets_fn: Callable[..., Any],
    get_enhancement_settings: Callable[[], Any] | None = None,
    get_multi_tier_buffer: Callable[[], Any] | None = None
) -> APIRouter:
    """
    Factory function to create player router with dependencies.

    Args:
        get_library_manager: Callable that returns the LibraryDatabase
        get_audio_player: Callable that returns AudioPlayer instance
        get_player_state_manager: Callable that returns PlayerStateManager instance
        connection_manager: WebSocket connection manager for broadcasts
        chunked_audio_processor_class: ChunkedAudioProcessor class (or None if not available)
        create_track_info_fn: Function to create TrackInfo from database track
        buffer_presets_fn: Function for proactive preset buffering

    Returns:
        APIRouter: Configured router instance
    """
    # chunked_audio_processor_class, buffer_presets_fn, get_enhancement_settings,
    # and get_multi_tier_buffer are accepted for call-site compatibility with
    # config/routes.py but are not used by any handler below -- pre-existing,
    # unrelated to #4670.
    _deps.get_library_manager = get_library_manager
    _deps.get_audio_player = get_audio_player
    _deps.get_player_state_manager = get_player_state_manager
    _deps.connection_manager = connection_manager
    _deps.create_track_info_fn = create_track_info_fn

    router = APIRouter(tags=["player"])

    # PLAYBACK
    router.add_api_route("/api/player/status", get_player_status, methods=["GET"], response_model=PlayerState)
    router.add_api_route("/api/player/load", load_track, methods=["POST"], response_model=LoadTrackResponse)
    router.add_api_route("/api/player/seek", seek_position, methods=["POST"], response_model=SeekResponse)
    router.add_api_route("/api/player/volume", set_volume, methods=["POST"], response_model=VolumeResponse)

    # QUEUE
    router.add_api_route("/api/player/queue", get_queue, methods=["GET"], response_model=QueueInfoResponse)
    router.add_api_route("/api/player/queue", set_queue, methods=["POST"], response_model=SetQueueResponse)

    # QUEUE HISTORY / UNDO (#3805) — registered before the `/queue/{index}`
    # DELETE route below; see the note above get_queue_history.
    router.add_api_route("/api/player/queue/history", get_queue_history, methods=["GET"], response_model=QueueHistoryListResponse)
    router.add_api_route("/api/player/queue/history", record_queue_history, methods=["POST"], response_model=QueueHistoryEntryResponse)
    router.add_api_route("/api/player/queue/undo", undo_queue_operation, methods=["POST"], response_model=UndoQueueResponse)
    router.add_api_route("/api/player/queue/history", clear_queue_history, methods=["DELETE"], response_model=MessageResponse)

    router.add_api_route("/api/player/queue/{index}", remove_from_queue, methods=["DELETE"], response_model=RemoveFromQueueResponse)
    router.add_api_route("/api/player/queue/reorder", reorder_queue, methods=["PUT"], response_model=QueueSizeResponse)
    router.add_api_route("/api/player/queue/clear", clear_queue, methods=["POST"], response_model=MessageResponse)
    router.add_api_route("/api/player/queue/add-track", add_track_to_queue, methods=["POST"], response_model=AddTrackToQueueResponse)
    router.add_api_route("/api/player/queue/move", move_queue_track, methods=["PUT"], response_model=MoveQueueTrackResponse)
    router.add_api_route("/api/player/queue/shuffle", shuffle_queue, methods=["POST"], response_model=QueueSizeResponse)
    router.add_api_route("/api/player/queue/repeat", set_repeat_mode, methods=["POST"], response_model=MessageResponse)

    # NAVIGATION
    router.add_api_route("/api/player/next", next_track, methods=["POST"], response_model=MessageResponse)
    router.add_api_route("/api/player/previous", previous_track, methods=["POST"], response_model=MessageResponse)

    return router
