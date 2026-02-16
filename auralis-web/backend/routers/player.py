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
- POST /api/player/play - Start playback
- POST /api/player/pause - Pause playback
- POST /api/player/stop - Stop playback
- POST /api/player/seek - Seek to position
- POST /api/player/volume - Set volume
- GET /api/player/queue - Get queue
- POST /api/player/queue - Set queue
- POST /api/player/queue/add - Add to queue
- DELETE /api/player/queue/{index} - Remove from queue
- PUT /api/player/queue/reorder - Reorder queue
- POST /api/player/queue/clear - Clear queue
- POST /api/player/queue/shuffle - Shuffle queue
- POST /api/player/next - Next track
- POST /api/player/previous - Previous track

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
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


def create_player_router(
    get_library_manager: Callable[[], Any],
    get_audio_player: Callable[[], Any],
    get_player_state_manager: Callable[[], Any],
    get_processing_cache: Callable[[], dict[str, Any]],
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
        get_audio_player: Callable that returns EnhancedAudioPlayer instance
        get_player_state_manager: Callable that returns PlayerStateManager instance
        get_processing_cache: Callable that returns processing cache dict
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

    # ============================================================================
    # PLAYBACK ENDPOINTS
    # ============================================================================

    @router.get("/api/player/status", response_model=None)
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
            raise HTTPException(status_code=500, detail=f"Failed to get player status: {e}")

    @router.post("/api/player/load", response_model=None)
    async def load_track(request: LoadTrackRequest, background_tasks: BackgroundTasks = None) -> dict[str, Any]:
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

        # Security: Query track from database to validate file path
        library_manager = get_library_manager()
        track = library_manager.tracks.get_by_id(request.track_id)
        if not track:
            raise HTTPException(status_code=404, detail=f"Track {request.track_id} not found in library")

        try:
            # Add to queue with track info dict (using validated filepath from database)
            track_info = {
                'filepath': track.filepath,  # Security: Use validated path from database
                'id': track.id
            }
            audio_player.add_to_queue(track_info)
            success = audio_player.load_current_track() if hasattr(audio_player, 'load_current_track') else True

            if success:
                # Broadcast to all connected clients
                await connection_manager.broadcast({
                    "type": "track_loaded",
                    "data": {"track_path": track.filepath}
                })

                # Generate mastering recommendation in background (Priority 4)
                if background_tasks:
                    service = get_recommendation_service()
                    background_tasks.add_task(
                        service.generate_and_broadcast_recommendation,
                        track_id=track.id,
                        track_path=track.filepath
                    )
                    logger.info(f"🎯 Scheduled mastering recommendation generation for track {track.id}")

                return {"message": "Track loaded successfully", "track_path": track.filepath}
            else:
                raise HTTPException(status_code=400, detail="Failed to load track")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load track: {e}")

    # ============================================================================
    # DEPRECATED: Legacy REST playback endpoints (replaced by WebSocket streaming)
    # ============================================================================
    # These endpoints have been replaced by WebSocket-based audio streaming.
    # Frontend now uses usePlayEnhanced hook which sends WebSocket messages
    # instead of REST API calls. Kept here temporarily for reference.
    # See: auralis-web/backend/routers/system.py - WebSocket endpoint handles 'play_enhanced' message
    # ============================================================================

    # @router.post("/api/player/play", response_model=None)
    # async def play_audio() -> Dict[str, Any]:
    #     """DEPRECATED: Use WebSocket 'play_enhanced' message instead."""
    #     raise HTTPException(
    #         status_code=410,
    #         detail="Endpoint deprecated. Use WebSocket streaming instead."
    #     )
    #     # Legacy implementation removed - audio playback now via WebSocket only

    # @router.post("/api/player/pause", response_model=None)
    # async def pause_audio() -> Dict[str, Any]:
    #     """DEPRECATED: Use usePlayEnhanced.pausePlayback() instead."""
    #     raise HTTPException(
    #         status_code=410,
    #         detail="Endpoint deprecated. Use WebSocket streaming pause control instead."
    #     )
    #     # Legacy implementation removed - pause now via usePlayEnhanced hook

    # @router.post("/api/player/stop", response_model=None)
    # async def stop_audio() -> Dict[str, Any]:
    #     """DEPRECATED: Use usePlayEnhanced.stopPlayback() instead."""
    #     raise HTTPException(
    #         status_code=410,
    #         detail="Endpoint deprecated. Use WebSocket streaming stop control instead."
    #     )
    #     # Legacy implementation removed - stop now via usePlayEnhanced hook

    @router.post("/api/player/seek", response_model=None)
    async def seek_position(position: float) -> dict[str, Any]:
        """
        Seek to position in seconds.

        Args:
            position: Position in seconds

        Returns:
            dict: Success message and new position
        """
        try:
            service = get_playback_service()
            result = await service.seek(position)
            return result
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to seek: {e}")

    # @router.get("/api/player/volume", response_model=None)
    # async def get_volume() -> Dict[str, Any]:
    #     """DEPRECATED: Volume now managed by usePlayEnhanced hook."""
    #     raise HTTPException(
    #         status_code=410,
    #         detail="Endpoint deprecated. Volume control now via WebSocket streaming."
    #     )
    #     # Legacy implementation removed - volume now via usePlayEnhanced.setVolume()

    # @router.post("/api/player/volume", response_model=None)
    # async def set_volume(volume: float) -> Dict[str, Any]:
    #     """DEPRECATED: Use usePlayEnhanced.setVolume() instead."""
    #     raise HTTPException(
    #         status_code=410,
    #         detail="Endpoint deprecated. Volume control now via WebSocket streaming."
    #     )
    #     # Legacy implementation removed - volume now via usePlayEnhanced.setVolume()

    # ============================================================================
    # QUEUE ENDPOINTS
    # ============================================================================

    @router.get("/api/player/queue", response_model=None)
    async def get_queue() -> dict[str, Any]:
        """Get current playback queue."""
        try:
            service = get_queue_service()
            return await service.get_queue_info()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get queue: {e}")

    @router.post("/api/player/queue", response_model=None)
    async def set_queue(request: SetQueueRequest) -> dict[str, Any]:
        """Set the playback queue (updates single source of truth)."""
        try:
            service = get_queue_service()
            return await service.set_queue(request.tracks, request.start_index)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e) if "valid" in str(e) else "Player not available")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to set queue: {e}")

    @router.post("/api/player/queue/add", response_model=None)
    async def add_to_queue(request: AddTrackToQueueRequest) -> dict[str, Any]:
        """Add track to playback queue (database-backed, prevents path traversal)."""
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        # Security: Query track from database to validate file path
        library_manager = get_library_manager()
        track = library_manager.tracks.get_by_id(request.track_id)
        if not track:
            raise HTTPException(status_code=404, detail=f"Track {request.track_id} not found in library")

        try:
            track_info = {"filepath": track.filepath, "id": track.id}  # Security: Use validated path from database
            audio_player.add_to_queue(track_info)

            await connection_manager.broadcast({
                "type": "queue_updated",
                "data": {"action": "added", "track_path": track.filepath}
            })

            return {"message": "Track added to queue", "track_path": track.filepath}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add to queue: {e}")

    @router.delete("/api/player/queue/{index}", response_model=None)
    async def remove_from_queue(index: int) -> dict[str, Any]:
        """Remove track from queue at specified index."""
        try:
            service = get_queue_service()
            return await service.remove_track_from_queue(index)
        except ValueError as e:
            status_code = 400 if "Invalid" in str(e) else 503
            raise HTTPException(status_code=status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to remove from queue: {e}")

    @router.put("/api/player/queue/reorder", response_model=None)
    async def reorder_queue(request: ReorderQueueRequest) -> dict[str, Any]:
        """Reorder the playback queue."""
        try:
            service = get_queue_service()
            return await service.reorder_queue(request.new_order)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reorder queue: {e}")

    @router.post("/api/player/queue/clear", response_model=None)
    async def clear_queue() -> dict[str, Any]:
        """Clear the entire playback queue."""
        try:
            service = get_queue_service()
            return await service.clear_queue()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to clear queue: {e}")

    @router.post("/api/player/queue/add-track", response_model=None)
    async def add_track_to_queue(request: AddTrackToQueueRequest) -> dict[str, Any]:
        """Add a track to queue at specific position (for drag-and-drop)."""
        try:
            service = get_queue_service()
            return await service.add_track_to_queue(request.track_id, request.position)
        except ValueError as e:
            status_code = 404 if "not found" in str(e).lower() else 503
            raise HTTPException(status_code=status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add track to queue: {e}")

    @router.put("/api/player/queue/move", response_model=None)
    async def move_queue_track(request: MoveQueueTrackRequest) -> dict[str, Any]:
        """Move a track within the queue (for drag-and-drop)."""
        try:
            service = get_queue_service()
            return await service.move_track_in_queue(request.from_index, request.to_index)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to move track: {e}")

    @router.post("/api/player/queue/shuffle", response_model=None)
    async def shuffle_queue() -> dict[str, Any]:
        """Shuffle the playback queue (keeps current track in place)."""
        try:
            service = get_queue_service()
            return await service.shuffle_queue()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to shuffle queue: {e}")

    # ============================================================================
    # NAVIGATION ENDPOINTS
    # ============================================================================

    @router.post("/api/player/next", response_model=None)
    async def next_track() -> dict[str, Any]:
        """Skip to next track."""
        try:
            service = get_navigation_service()
            return await service.next_track()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to skip track: {e}")

    @router.post("/api/player/previous", response_model=None)
    async def previous_track() -> dict[str, Any]:
        """Skip to previous track."""
        try:
            service = get_navigation_service()
            return await service.previous_track()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to skip track: {e}")

    return router
