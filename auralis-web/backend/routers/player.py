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
from typing import Any, Literal, cast
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
from player_state import PlayerState, TrackInfo
from services import (
    NavigationService,
    PlaybackService,
    QueueService,
    RecommendationService,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["player"])


class SetQueueRequest(BaseModel):
    """Request model for setting the playback queue"""
    tracks: list[int]  # Track IDs
    start_index: int = 0


class ReorderQueueRequest(BaseModel):
    """Request model for reordering the queue"""
    new_order: list[int]  # New order of track indices


class MoveQueueTrackRequest(BaseModel):
    """Request model for moving a track within the queue (drag-and-drop)"""
    from_index: int
    to_index: int


class AddTrackToQueueRequest(BaseModel):
    """Request model for adding a track to queue with position"""
    track_id: int
    position: int | None = None  # None = append to end


class LoadTrackRequest(BaseModel):
    """Request model for loading a track"""
    track_id: int


class SeekRequest(BaseModel):
    """Request model for seek operation with input validation."""
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
    volume: float

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
    track_ids: list[int]
    current_index: int = 0
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
    repeat_enabled: bool | None = None

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
        get_library_manager: Callable that returns LibraryManager instance
        get_audio_player: Callable that returns AudioPlayer instance
        get_player_state_manager: Callable that returns PlayerStateManager instance
        connection_manager: WebSocket connection manager for broadcasts
        chunked_audio_processor_class: ChunkedAudioProcessor class (or None if not available)
        create_track_info_fn: Function to create TrackInfo from database track
        buffer_presets_fn: Function for proactive preset buffering

    Returns:
        APIRouter: Configured router instance
    """

    # Initialize services
    def get_playback_service() -> PlaybackService:
        """Lazy service initialization"""
        return PlaybackService(
            audio_player=get_audio_player(),
            player_state_manager=get_player_state_manager(),
            connection_manager=connection_manager
        )

    def get_queue_service() -> QueueService:
        """Lazy service initialization"""
        return QueueService(
            audio_player=get_audio_player(),
            player_state_manager=get_player_state_manager(),
            library_manager=get_library_manager(),
            connection_manager=connection_manager,
            create_track_info_fn=create_track_info_fn
        )

    def get_recommendation_service() -> RecommendationService:
        """Lazy service initialization"""
        return RecommendationService(
            connection_manager=connection_manager
        )

    def get_navigation_service() -> NavigationService:
        """Lazy service initialization"""
        return NavigationService(
            audio_player=get_audio_player(),
            player_state_manager=get_player_state_manager(),
            connection_manager=connection_manager,
            create_track_info_fn=create_track_info_fn
        )

    def get_queue_history_repo() -> Any:
        """Lazy repository initialization (#3805).

        Constructed directly from the library manager's session factory
        rather than via RepositoryFactory — this router only receives
        get_library_manager, not get_repository_factory. QueueHistoryRepository
        is cheap to construct (BaseRepository just holds the session factory;
        no per-instance caching needed for occasional undo/history calls).
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")
        from auralis.library.repositories.queue_history_repository import (
            QueueHistoryRepository,
        )
        return QueueHistoryRepository(library_manager.SessionLocal)

    # ============================================================================
    # PLAYBACK ENDPOINTS
    # ============================================================================

    @router.get("/api/player/status", response_model=PlayerState)
    async def get_player_status() -> dict[str, Any]:
        """
        Get current player status (single source of truth).

        Returns:
            dict: Player state with track info, playback status, queue

        Raises:
            HTTPException: If player not available or query fails
        """
        try:
            service = get_playback_service()
            return await service.get_status()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error("Failed to get player status", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to get player status")

    @router.post("/api/player/load", response_model=LoadTrackResponse)
    async def load_track(request: LoadTrackRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
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
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        # Security: Query track from database to validate file path (offloaded — sync DB call)
        library_manager = get_library_manager()
        track = await asyncio.to_thread(library_manager.tracks.get_by_id, request.track_id)
        if not track:
            raise HTTPException(status_code=404, detail=f"Track {request.track_id} not found in library")

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
                service = get_recommendation_service()
                background_tasks.add_task(
                    service.generate_and_broadcast_recommendation,
                    track_id=track.id,
                    track_path=track.filepath
                )
                logger.info(f"🎯 Scheduled mastering recommendation generation for track {track.id}")

                return {"message": "Track loaded successfully", "track_id": track.id}
            else:
                raise HTTPException(status_code=400, detail="Failed to load track")

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to load track", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to load track")

    @router.post("/api/player/seek", response_model=SeekResponse)
    async def seek_position(request: SeekRequest) -> dict[str, Any]:
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
        state_manager = get_player_state_manager()
        if state_manager:
            state = state_manager.get_state()
            if state.duration > 0 and position > state.duration:
                raise HTTPException(
                    status_code=400,
                    detail=f"Position {position:.1f}s exceeds track duration {state.duration:.1f}s"
                )

        try:
            service = get_playback_service()
            result = await service.seek(position)
            return result
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error("Failed to seek", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to seek")

    @router.post("/api/player/volume", response_model=VolumeResponse)
    async def set_volume(body: SetVolumeRequest) -> dict[str, Any]:
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
            service = get_playback_service()
            # Convert 0-100 to 0.0-1.0 for service layer (clamping already done by model)
            normalized_volume = body.volume / 100.0
            result = await service.set_volume(normalized_volume)
            # Convert back to 0-100 for API response (fixes #3204)
            result["volume"] = body.volume
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to set volume", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to set volume")

    # ============================================================================
    # QUEUE ENDPOINTS
    # ============================================================================

    @router.get("/api/player/queue", response_model=QueueInfoResponse)
    async def get_queue() -> dict[str, Any]:
        """Get current playback queue."""
        try:
            service = get_queue_service()
            return await service.get_queue_info()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error("Failed to get queue", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to get queue")

    @router.post("/api/player/queue", response_model=SetQueueResponse)
    async def set_queue(request: SetQueueRequest) -> dict[str, Any]:
        """Set the playback queue (updates single source of truth)."""
        try:
            service = get_queue_service()
            return await service.set_queue(request.tracks, request.start_index)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e) if "valid" in str(e) else "Player not available")
        except Exception as e:
            logger.error("Failed to set queue", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to set queue")

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

    @router.get("/api/player/queue/history", response_model=QueueHistoryListResponse)
    async def get_queue_history(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
        """Get recent queue-operation history entries (newest first)."""
        try:
            repo = get_queue_history_repo()
            entries = await asyncio.to_thread(repo.get_history, limit)
            history = [entry.to_dict() for entry in entries]
            return {"history": history, "count": len(history)}
        except HTTPException:
            raise
        except Exception:
            logger.error("Failed to get queue history", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to get queue history")

    @router.post("/api/player/queue/history", response_model=QueueHistoryEntryResponse)
    async def record_queue_history(request: RecordQueueHistoryRequest) -> dict[str, Any]:
        """Record a queue-state snapshot to history, for later undo."""
        try:
            repo = get_queue_history_repo()
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
        except Exception:
            logger.error("Failed to record queue history", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to record queue history")

    @router.post("/api/player/queue/undo", response_model=UndoQueueResponse)
    async def undo_queue_operation() -> dict[str, Any]:
        """Undo the last recorded queue operation.

        Restores both the persisted QueueState row and the live queue
        (track order + position via QueueService.set_queue, repeat/shuffle
        flags via PlayerStateManager) — restoring only the DB snapshot would
        make "undo" silently do nothing from the user's perspective (#3805).
        """
        try:
            repo = get_queue_history_repo()
            restored = await asyncio.to_thread(repo.undo)
            if restored is None:
                raise HTTPException(status_code=404, detail="No history available to undo")

            restored_dict = restored.to_dict()

            try:
                queue_service = get_queue_service()
                await queue_service.set_queue(
                    restored_dict['track_ids'], start_index=restored_dict['current_index']
                )
            except ValueError as e:
                # Audio player / state manager not available — the DB state
                # was still restored; degrade gracefully rather than failing
                # the whole undo over a live-sync step.
                logger.warning(f"Queue history restored in DB but live queue sync skipped: {e}")

            state_manager = get_player_state_manager()
            if state_manager:
                await state_manager.update_state(
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
        except Exception:
            logger.error("Failed to undo queue operation", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to undo queue operation")

    @router.delete("/api/player/queue/history", response_model=MessageResponse)
    async def clear_queue_history() -> dict[str, Any]:
        """Clear all queue history entries."""
        try:
            repo = get_queue_history_repo()
            await asyncio.to_thread(repo.clear_history)
            return {"message": "Queue history cleared"}
        except HTTPException:
            raise
        except Exception:
            logger.error("Failed to clear queue history", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to clear queue history")

    @router.delete("/api/player/queue/{index}", response_model=RemoveFromQueueResponse)
    async def remove_from_queue(index: int) -> dict[str, Any]:
        """Remove track from queue at specified index."""
        try:
            service = get_queue_service()
            return await service.remove_track_from_queue(index)
        except ValueError as e:
            status_code = 400 if "Invalid" in str(e) else 503
            raise HTTPException(status_code=status_code, detail=str(e))
        except Exception as e:
            logger.error("Failed to remove from queue", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to remove from queue")

    @router.put("/api/player/queue/reorder", response_model=QueueSizeResponse)
    async def reorder_queue(request: ReorderQueueRequest) -> dict[str, Any]:
        """Reorder the playback queue."""
        try:
            service = get_queue_service()
            return await service.reorder_queue(request.new_order)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to reorder queue", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to reorder queue")

    @router.post("/api/player/queue/clear", response_model=MessageResponse)
    async def clear_queue() -> dict[str, Any]:
        """Clear the entire playback queue."""
        try:
            service = get_queue_service()
            return await service.clear_queue()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error("Failed to clear queue", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to clear queue")

    @router.post("/api/player/queue/add-track", response_model=AddTrackToQueueResponse)
    async def add_track_to_queue(request: AddTrackToQueueRequest) -> dict[str, Any]:
        """Add a track to queue at specific position (for drag-and-drop)."""
        try:
            service = get_queue_service()
            return await service.add_track_to_queue(request.track_id, request.position)
        except ValueError as e:
            status_code = 404 if "not found" in str(e).lower() else 503
            raise HTTPException(status_code=status_code, detail=str(e))
        except Exception as e:
            logger.error("Failed to add track to queue", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to add track to queue")

    @router.put("/api/player/queue/move", response_model=MoveQueueTrackResponse)
    async def move_queue_track(request: MoveQueueTrackRequest) -> dict[str, Any]:
        """Move a track within the queue (for drag-and-drop)."""
        try:
            service = get_queue_service()
            return await service.move_track_in_queue(request.from_index, request.to_index)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to move track", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to move track")

    @router.post("/api/player/queue/shuffle", response_model=QueueSizeResponse)
    async def shuffle_queue(request: ShuffleRequest) -> dict[str, Any]:
        """Shuffle or unshuffle the playback queue."""
        try:
            service = get_queue_service()
            if request.enabled:
                return await service.shuffle_queue()
            else:
                return await service.unshuffle_queue()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error("Failed to shuffle queue", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to shuffle queue")

    @router.post("/api/player/queue/repeat", response_model=MessageResponse)
    async def set_repeat_mode(request: RepeatModeRequest) -> dict[str, Any]:
        """Set the playback repeat mode (off, all, one)."""
        try:
            state_manager = get_player_state_manager()
            if not state_manager:
                raise ValueError("Player state manager not available")

            # Pass through 'off' / 'one' / 'all' — backend now uses the same
            # vocabulary as the frontend Literal (#3501 / BE-NEW-43).
            await state_manager.update_state(repeat_mode=request.mode)

            # Broadcast canonical value so WS and REST always agree
            await connection_manager.broadcast({
                "type": "repeat_mode_changed",
                "data": {"repeat_mode": request.mode},
            })

            return {"message": f"Repeat mode set to {request.mode}"}
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception:
            logger.error("Failed to set repeat mode", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to set repeat mode")

    # ============================================================================
    # NAVIGATION ENDPOINTS
    # ============================================================================

    @router.post("/api/player/next", response_model=MessageResponse)
    async def next_track() -> dict[str, Any]:
        """Skip to next track."""
        try:
            service = get_navigation_service()
            return await service.next_track()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error("Failed to skip track", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to skip track")

    @router.post("/api/player/previous", response_model=MessageResponse)
    async def previous_track() -> dict[str, Any]:
        """Skip to previous track."""
        try:
            service = get_navigation_service()
            return await service.previous_track()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error("Failed to skip track", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to skip track")

    return router
