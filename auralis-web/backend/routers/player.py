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

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Callable, Any, Dict
import logging
import os

from services import (
    PlaybackService,
    QueueService,
    RecommendationService,
    NavigationService
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["player"])


class SetQueueRequest(BaseModel):
    """Request model for setting the playback queue"""
    tracks: List[int]  # Track IDs
    start_index: int = 0


class ReorderQueueRequest(BaseModel):
    """Request model for reordering the queue"""
    new_order: List[int]  # New order of track indices


class MoveQueueTrackRequest(BaseModel):
    """Request model for moving a track within the queue (drag-and-drop)"""
    from_index: int
    to_index: int


class AddTrackToQueueRequest(BaseModel):
    """Request model for adding a track to queue with position"""
    track_id: int
    position: Optional[int] = None  # None = append to end


def create_player_router(
    get_library_manager: Callable[[], Any],
    get_audio_player: Callable[[], Any],
    get_player_state_manager: Callable[[], Any],
    get_processing_cache: Callable[[], Dict[str, Any]],
    connection_manager: Any,
    chunked_audio_processor_class: Optional[type],
    create_track_info_fn: Callable[[Any], Any],
    buffer_presets_fn: Callable[..., Any],
    get_multi_tier_buffer: Optional[Callable[[], Any]] = None,
    get_enhancement_settings: Optional[Callable[[], Any]] = None
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
        get_multi_tier_buffer: Callable that returns MultiTierBufferManager (optional)

    Returns:
        APIRouter: Configured router instance
    """

    # Initialize services
    def get_playback_service() -> PlaybackService:  # type: ignore[no-untyped-def]
        """Lazy service initialization"""
        return PlaybackService(  # type: ignore[no-untyped-call]
            audio_player=get_audio_player(),
            player_state_manager=get_player_state_manager(),
            connection_manager=connection_manager
        )

    def get_queue_service() -> QueueService:  # type: ignore[no-untyped-def]
        """Lazy service initialization"""
        return QueueService(  # type: ignore[no-untyped-call]
            audio_player=get_audio_player(),
            player_state_manager=get_player_state_manager(),
            library_manager=get_library_manager(),
            connection_manager=connection_manager,
            create_track_info_fn=create_track_info_fn
        )

    def get_recommendation_service() -> RecommendationService:  # type: ignore[no-untyped-def]
        """Lazy service initialization"""
        return RecommendationService(  # type: ignore[no-untyped-call]
            connection_manager=connection_manager
        )

    def get_navigation_service() -> NavigationService:  # type: ignore[no-untyped-def]
        """Lazy service initialization"""
        return NavigationService(  # type: ignore[no-untyped-call]
            audio_player=get_audio_player(),
            player_state_manager=get_player_state_manager(),
            library_manager=get_library_manager(),
            connection_manager=connection_manager,
            create_track_info_fn=create_track_info_fn
        )

    # ============================================================================
    # PLAYBACK ENDPOINTS
    # ============================================================================

    @router.get("/api/player/status")
    async def get_player_status():
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

    @router.post("/api/player/load")
    async def load_track(track_path: str, track_id: Optional[int] = None, background_tasks: Optional[BackgroundTasks] = None) -> Dict[str, Any]:
        """
        Load a track into the player.

        Also generates and broadcasts mastering profile recommendation (Priority 4) in background.

        Args:
            track_path: Path to audio file
            track_id: Optional track database ID (used for mastering recommendation)
            background_tasks: FastAPI background tasks

        Returns:
            dict: Success message

        Raises:
            HTTPException: If audio player not available or load fails
        """
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            # Add to queue with track info dict
            track_info = {
                'filepath': track_path,
                'id': track_id
            }
            audio_player.add_to_queue(track_info)
            success = audio_player.load_current_track() if hasattr(audio_player, 'load_current_track') else True

            if success:
                # Broadcast to all connected clients
                await connection_manager.broadcast({
                    "type": "track_loaded",
                    "data": {"track_path": track_path}
                })

                # Generate mastering recommendation in background (Priority 4)
                if track_id is not None and background_tasks:
                    service = get_recommendation_service()
                    background_tasks.add_task(
                        service.generate_and_broadcast_recommendation,
                        track_id=track_id,
                        track_path=track_path
                    )
                    logger.info(f"🎯 Scheduled mastering recommendation generation for track {track_id}")

                return {"message": "Track loaded successfully", "track_path": track_path}
            else:
                raise HTTPException(status_code=400, detail="Failed to load track")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load track: {e}")

    @router.post("/api/player/play")
    async def play_audio():
        """Start playback (updates single source of truth)."""
        try:
            service = get_playback_service()
            return await service.play()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start playback: {e}")

    @router.post("/api/player/pause")
    async def pause_audio():
        """Pause playback (updates single source of truth)."""
        try:
            service = get_playback_service()
            return await service.pause()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to pause playback: {e}")

    @router.post("/api/player/stop")
    async def stop_audio():
        """Stop playback."""
        try:
            service = get_playback_service()
            return await service.stop()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop playback: {e}")

    @router.post("/api/player/seek")
    async def seek_position(position: float):
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

            # Update multi-tier buffer with new position (for branch prediction)
            if get_multi_tier_buffer and get_enhancement_settings:
                player_state_manager = get_player_state_manager()
                if player_state_manager:
                    buffer_manager = get_multi_tier_buffer()
                    if buffer_manager:
                        state = player_state_manager.get_state()
                        if state.current_track:
                            settings = get_enhancement_settings()
                            await buffer_manager.update_position(
                                track_id=state.current_track.id,
                                position=position,
                                preset=settings.get("preset", "adaptive"),
                                intensity=settings.get("intensity", 1.0)
                            )
                            logger.debug(f"Buffer manager updated: track={state.current_track.id}, position={position:.1f}s")

            return result
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to seek: {e}")

    @router.get("/api/player/volume")
    async def get_volume():
        """Get current playback volume (0.0 to 1.0)."""
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            volume = getattr(audio_player, 'volume', 0.5)
            return {"volume": volume}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get volume: {e}")

    @router.post("/api/player/volume")
    async def set_volume(volume: float):
        """Set playback volume (0.0 to 1.0)."""
        try:
            service = get_playback_service()
            return await service.set_volume(volume)
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to set volume: {e}")

    # ============================================================================
    # QUEUE ENDPOINTS
    # ============================================================================

    @router.get("/api/player/queue")
    async def get_queue():
        """Get current playback queue."""
        try:
            service = get_queue_service()
            return await service.get_queue_info()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get queue: {e}")

    @router.post("/api/player/queue")
    async def set_queue(request: SetQueueRequest):
        """Set the playback queue (updates single source of truth)."""
        try:
            service = get_queue_service()
            return await service.set_queue(request.tracks, request.start_index)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e) if "valid" in str(e) else "Player not available")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to set queue: {e}")

    @router.post("/api/player/queue/add")
    async def add_to_queue(track_path: str):
        """Add track to playback queue."""
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            track_info = {"filepath": track_path}
            audio_player.add_to_queue(track_info)

            await connection_manager.broadcast({
                "type": "queue_updated",
                "data": {"action": "added", "track_path": track_path}
            })

            return {"message": "Track added to queue", "track_path": track_path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add to queue: {e}")

    @router.delete("/api/player/queue/{index}")
    async def remove_from_queue(index: int):
        """Remove track from queue at specified index."""
        try:
            service = get_queue_service()
            return await service.remove_track_from_queue(index)
        except ValueError as e:
            status_code = 400 if "Invalid" in str(e) else 503
            raise HTTPException(status_code=status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to remove from queue: {e}")

    @router.put("/api/player/queue/reorder")
    async def reorder_queue(request: ReorderQueueRequest):
        """Reorder the playback queue."""
        try:
            service = get_queue_service()
            return await service.reorder_queue(request.new_order)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reorder queue: {e}")

    @router.post("/api/player/queue/clear")
    async def clear_queue():
        """Clear the entire playback queue."""
        try:
            service = get_queue_service()
            return await service.clear_queue()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to clear queue: {e}")

    @router.post("/api/player/queue/add-track")
    async def add_track_to_queue(request: AddTrackToQueueRequest):
        """Add a track to queue at specific position (for drag-and-drop)."""
        try:
            service = get_queue_service()
            return await service.add_track_to_queue(request.track_id, request.position)
        except ValueError as e:
            status_code = 404 if "not found" in str(e).lower() else 503
            raise HTTPException(status_code=status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add track to queue: {e}")

    @router.put("/api/player/queue/move")
    async def move_queue_track(request: MoveQueueTrackRequest):
        """Move a track within the queue (for drag-and-drop)."""
        try:
            service = get_queue_service()
            return await service.move_track_in_queue(request.from_index, request.to_index)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to move track: {e}")

    @router.post("/api/player/queue/shuffle")
    async def shuffle_queue():
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

    @router.post("/api/player/next")
    async def next_track():
        """Skip to next track."""
        try:
            service = get_navigation_service()
            return await service.next_track()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to skip track: {e}")

    @router.post("/api/player/previous")
    async def previous_track():
        """Skip to previous track."""
        try:
            service = get_navigation_service()
            return await service.previous_track()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to skip track: {e}")

    return router
