"""
Player Router
~~~~~~~~~~~~~

Handles audio playback control and queue management.

Endpoints:
- GET /api/player/status - Get current player status
- GET /api/player/stream/{track_id} - Stream audio file (with optional enhancement)
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
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import logging
import os

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
    get_library_manager,
    get_audio_player,
    get_player_state_manager,
    get_processing_cache,
    connection_manager,
    chunked_audio_processor_class,
    create_track_info_fn,
    buffer_presets_fn,
    get_multi_tier_buffer=None,
    get_enhancement_settings=None
):
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

    @router.get("/api/player/status")
    async def get_player_status():
        """
        Get current player status (single source of truth).

        Returns:
            dict: Player state with track info, playback status, queue

        Raises:
            HTTPException: If player not available or query fails
        """
        player_state_manager = get_player_state_manager()
        if not player_state_manager:
            raise HTTPException(status_code=503, detail="Player not available")

        try:
            # Return current state from state manager
            state = player_state_manager.get_state()
            return state.model_dump()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get player status: {e}")

    @router.get("/api/player/stream/{track_id}")
    async def stream_audio(
        track_id: int,
        enhanced: bool = False,
        preset: str = "adaptive",
        intensity: float = 1.0,
        background_tasks: BackgroundTasks = None
    ):
        """
        Stream audio file to frontend for playback via HTML5 Audio API.

        Supports real-time audio enhancement with Auralis processing using
        chunked streaming for fast playback start.

        Args:
            track_id: Track ID from library
            enhanced: Enable Auralis processing (default: False)
            preset: Processing preset - adaptive, gentle, warm, bright, punchy (default: adaptive)
            intensity: Processing intensity 0.0-1.0 (default: 1.0)
            background_tasks: FastAPI background tasks for async chunk processing

        Returns:
            FileResponse: Audio file stream with appropriate headers

        Performance:
            - Without enhancement: Streams original file immediately
            - With enhancement (chunked): Processes first 30s chunk (~1s), then streams
            - Background processes remaining chunks while user listens

        Raises:
            HTTPException: If library not available, track not found, or streaming fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library not available")

        try:
            # Get track from library
            track = library_manager.tracks.get_by_id(track_id)
            if not track:
                raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

            # Check if file exists
            if not os.path.exists(track.filepath):
                raise HTTPException(status_code=404, detail=f"Audio file not found: {track.filepath}")

            # If enhancement is requested, use chunked processing
            if enhanced:
                # OPTIMIZATION: Check if full file already exists FIRST
                # This enables instant preset switching if chunks were pre-buffered
                if chunked_audio_processor_class is None:
                    raise HTTPException(status_code=503, detail="Chunked processing not available")

                # Create processor to check for cached full file
                processor = chunked_audio_processor_class(
                    track_id=track_id,
                    filepath=track.filepath,
                    preset=preset,
                    intensity=intensity,
                    chunk_cache=get_processing_cache()
                )

                # Check if we have a cached full file
                full_path = processor.chunk_dir / f"track_{track_id}_{processor.file_signature}_{preset}_{intensity}_full.wav"

                if full_path.exists():
                    # INSTANT! Fully processed file exists from previous playback or proactive buffering
                    logger.info(f"⚡ INSTANT: Serving cached full file for preset '{preset}'")
                    file_to_serve = str(full_path)
                else:
                    # Need to process - log which preset and how many chunks
                    logger.info(f"Processing track {track_id} (preset: {preset}, {processor.total_chunks} chunks)")

                    # Process all chunks and concatenate
                    # This is needed because HTML5 Audio API requires complete files
                    file_to_serve = processor.get_full_processed_audio_path()

                    # Start proactive buffering of OTHER presets in background
                    if background_tasks and buffer_presets_fn:
                        background_tasks.add_task(
                            buffer_presets_fn,
                            track_id=track_id,
                            filepath=track.filepath,
                            intensity=intensity,
                            total_chunks=processor.total_chunks
                        )
                        logger.info(f"🚀 Proactive buffering started for other presets")

                # Cache the full file path
                processing_cache = get_processing_cache()
                cache_key = f"{track_id}_{preset}_{intensity}"
                processing_cache[cache_key] = file_to_serve
            else:
                # No enhancement - serve original file
                file_to_serve = track.filepath

            # Determine MIME type based on file extension
            ext = os.path.splitext(file_to_serve)[1].lower()
            mime_types = {
                '.mp3': 'audio/mpeg',
                '.flac': 'audio/flac',
                '.wav': 'audio/wav',
                '.ogg': 'audio/ogg',
                '.m4a': 'audio/mp4',
                '.aac': 'audio/aac'
            }
            media_type = mime_types.get(ext, 'audio/wav')

            # Return the audio file with proper headers for streaming
            return FileResponse(
                file_to_serve,
                media_type=media_type,
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Disposition": f"inline; filename=\"{os.path.basename(file_to_serve)}\"",
                    "X-Enhanced": "true" if enhanced else "false",
                    "X-Preset": preset if enhanced else "none",
                    "X-Chunked": "true" if (enhanced and chunked_audio_processor_class) else "false"
                }
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to stream audio: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to stream audio: {e}")

    @router.post("/api/player/load")
    async def load_track(track_path: str):
        """
        Load a track into the player.

        Args:
            track_path: Path to audio file

        Returns:
            dict: Success message

        Raises:
            HTTPException: If audio player not available or load fails
        """
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            # Add to queue and load
            audio_player.add_to_queue(track_path)
            success = audio_player.load_current_track() if hasattr(audio_player, 'load_current_track') else True

            if success:
                # Broadcast to all connected clients
                await connection_manager.broadcast({
                    "type": "track_loaded",
                    "data": {"track_path": track_path}
                })
                return {"message": "Track loaded successfully", "track_path": track_path}
            else:
                raise HTTPException(status_code=400, detail="Failed to load track")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load track: {e}")

    @router.post("/api/player/play")
    async def play_audio():
        """
        Start playback (updates single source of truth).

        Returns:
            dict: Success message and playback state

        Raises:
            HTTPException: If player not available or playback fails
        """
        player_state_manager = get_player_state_manager()
        audio_player = get_audio_player()

        if not player_state_manager:
            raise HTTPException(status_code=503, detail="Player not available")
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            audio_player.play()

            # Update state (broadcasts automatically)
            await player_state_manager.set_playing(True)

            # Broadcast playback_started event
            await connection_manager.broadcast({
                "type": "playback_started",
                "data": {"state": "playing"}
            })

            return {"message": "Playback started", "state": "playing"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start playback: {e}")

    @router.post("/api/player/pause")
    async def pause_audio():
        """
        Pause playback (updates single source of truth).

        Returns:
            dict: Success message and playback state

        Raises:
            HTTPException: If player not available or pause fails
        """
        player_state_manager = get_player_state_manager()
        audio_player = get_audio_player()

        if not player_state_manager:
            raise HTTPException(status_code=503, detail="Player not available")
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            audio_player.pause()

            # Update state (broadcasts automatically)
            await player_state_manager.set_playing(False)

            # Broadcast playback_paused event
            await connection_manager.broadcast({
                "type": "playback_paused",
                "data": {"state": "paused"}
            })

            return {"message": "Playback paused", "state": "paused"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to pause playback: {e}")

    @router.post("/api/player/stop")
    async def stop_audio():
        """
        Stop playback.

        Returns:
            dict: Success message and playback state

        Raises:
            HTTPException: If audio player not available or stop fails
        """
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            audio_player.stop()

            # Broadcast to all connected clients
            await connection_manager.broadcast({
                "type": "playback_stopped",
                "data": {"state": "stopped"}
            })

            return {"message": "Playback stopped", "state": "stopped"}
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

        Raises:
            HTTPException: If audio player not available or seek fails
        """
        audio_player = get_audio_player()
        player_state_manager = get_player_state_manager()

        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            if hasattr(audio_player, 'seek_to_position'):
                audio_player.seek_to_position(position)

            # Update multi-tier buffer with new position (for branch prediction)
            if get_multi_tier_buffer and get_enhancement_settings and player_state_manager:
                buffer_manager = get_multi_tier_buffer()
                if buffer_manager:
                    state = player_state_manager.get_state()
                    # Only update if we have a current track
                    if state.current_track:
                        settings = get_enhancement_settings()
                        await buffer_manager.update_position(
                            track_id=state.current_track.id,
                            position=position,
                            preset=settings.get("preset", "adaptive"),
                            intensity=settings.get("intensity", 1.0)
                        )
                        logger.debug(f"Buffer manager updated: track={state.current_track.id}, position={position:.1f}s")

            # Broadcast to all connected clients
            await connection_manager.broadcast({
                "type": "position_changed",
                "data": {"position": position}
            })

            return {"message": "Position updated", "position": position}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to seek: {e}")

    @router.post("/api/player/volume")
    async def set_volume(volume: float):
        """
        Set playback volume (0.0 to 1.0).

        Args:
            volume: Volume level (0.0 to 1.0)

        Returns:
            dict: Success message and new volume

        Raises:
            HTTPException: If audio player not available or volume change fails
        """
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            # Clamp volume to valid range
            volume = max(0.0, min(1.0, volume))

            if hasattr(audio_player, 'set_volume'):
                audio_player.set_volume(volume)

            # Broadcast to all connected clients
            await connection_manager.broadcast({
                "type": "volume_changed",
                "data": {"volume": volume}
            })

            return {"message": "Volume updated", "volume": volume}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to set volume: {e}")

    @router.get("/api/player/queue")
    async def get_queue():
        """
        Get current playback queue.

        Returns:
            dict: Queue info with tracks and current index

        Raises:
            HTTPException: If audio player not available or query fails
        """
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            if hasattr(audio_player, 'queue_manager'):
                queue_info = audio_player.queue_manager.get_queue_info() if hasattr(audio_player.queue_manager, 'get_queue_info') else {
                    "tracks": list(audio_player.queue_manager.queue),
                    "current_index": audio_player.queue_manager.current_index,
                    "total_tracks": len(audio_player.queue_manager.queue)
                }
                return queue_info
            else:
                return {"tracks": [], "current_index": 0, "total_tracks": 0}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get queue: {e}")

    @router.post("/api/player/queue")
    async def set_queue(request: SetQueueRequest):
        """
        Set the playback queue (updates single source of truth).

        Args:
            request: Queue data with track IDs and start index

        Returns:
            dict: Success message and queue info

        Raises:
            HTTPException: If player/library not available or operation fails
        """
        player_state_manager = get_player_state_manager()
        library_manager = get_library_manager()
        audio_player = get_audio_player()

        if not player_state_manager:
            raise HTTPException(status_code=503, detail="Player not available")
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            # Get tracks from library by IDs
            db_tracks = []
            for track_id in request.tracks:
                track = library_manager.tracks.get_by_id(track_id)
                if track:
                    db_tracks.append(track)

            if not db_tracks:
                raise HTTPException(status_code=400, detail="No valid tracks found")

            # Convert to TrackInfo for state
            track_infos = [create_track_info_fn(t) for t in db_tracks]
            track_infos = [t for t in track_infos if t is not None]

            # Update state manager (this broadcasts automatically)
            await player_state_manager.set_queue(track_infos, request.start_index)

            # Set queue in actual player
            if hasattr(audio_player, 'queue_manager'):
                audio_player.queue_manager.set_queue([t.filepath for t in db_tracks], request.start_index)

            # Load and start playing if requested
            if request.start_index >= 0 and request.start_index < len(db_tracks):
                current_track = db_tracks[request.start_index]

                # Update state with current track
                await player_state_manager.set_track(current_track, library_manager)

                # Load the track in player
                audio_player.load_file(current_track.filepath)

                # Start playback
                audio_player.play()

                # Update playing state
                await player_state_manager.set_playing(True)

            return {
                "message": "Queue set successfully",
                "track_count": len(track_infos),
                "start_index": request.start_index
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to set queue: {e}")

    @router.post("/api/player/queue/add")
    async def add_to_queue(track_path: str):
        """
        Add track to playback queue.

        Args:
            track_path: Path to audio file

        Returns:
            dict: Success message

        Raises:
            HTTPException: If audio player not available or operation fails
        """
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            # add_to_queue expects a dict with track info, not a string path
            # Create a minimal track info dict with the filepath
            track_info = {"filepath": track_path}
            audio_player.add_to_queue(track_info)

            # Broadcast queue update
            await connection_manager.broadcast({
                "type": "queue_updated",
                "data": {"action": "added", "track_path": track_path}
            })

            return {"message": "Track added to queue", "track_path": track_path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add to queue: {e}")

    @router.delete("/api/player/queue/{index}")
    async def remove_from_queue(index: int):
        """
        Remove track from queue at specified index.

        Args:
            index: Track index to remove

        Returns:
            dict: Success message and updated queue size

        Raises:
            HTTPException: If player not available, invalid index, or operation fails
        """
        player_state_manager = get_player_state_manager()
        audio_player = get_audio_player()

        if not player_state_manager:
            raise HTTPException(status_code=503, detail="Player not available")
        if not audio_player or not hasattr(audio_player, 'queue_manager'):
            raise HTTPException(status_code=503, detail="Queue manager not available")

        try:
            queue_manager = audio_player.queue_manager

            # Validate index
            if index < 0 or index >= queue_manager.get_queue_size():
                raise HTTPException(status_code=400, detail=f"Invalid index: {index}")

            # Remove track from queue
            success = queue_manager.remove_track(index)

            if not success:
                raise HTTPException(status_code=400, detail="Failed to remove track")

            # Get updated queue
            updated_queue = queue_manager.get_queue()

            # Broadcast queue update
            await connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "removed",
                    "index": index,
                    "queue_size": len(updated_queue)
                }
            })

            return {
                "message": "Track removed from queue",
                "index": index,
                "queue_size": len(updated_queue)
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to remove from queue: {e}")

    @router.put("/api/player/queue/reorder")
    async def reorder_queue(request: ReorderQueueRequest):
        """
        Reorder the playback queue.

        Args:
            request: New order of track indices

        Returns:
            dict: Success message and queue size

        Raises:
            HTTPException: If player not available, invalid order, or operation fails
        """
        player_state_manager = get_player_state_manager()
        audio_player = get_audio_player()

        if not player_state_manager:
            raise HTTPException(status_code=503, detail="Player not available")
        if not audio_player or not hasattr(audio_player, 'queue_manager'):
            raise HTTPException(status_code=503, detail="Queue manager not available")

        try:
            queue_manager = audio_player.queue_manager

            # Validate new_order
            queue_size = queue_manager.get_queue_size()
            if len(request.new_order) != queue_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"new_order length ({len(request.new_order)}) must match queue size ({queue_size})"
                )

            if set(request.new_order) != set(range(queue_size)):
                raise HTTPException(
                    status_code=400,
                    detail="new_order must contain all indices from 0 to queue_size-1 exactly once"
                )

            # Reorder queue
            success = queue_manager.reorder_tracks(request.new_order)

            if not success:
                raise HTTPException(status_code=400, detail="Failed to reorder queue")

            # Get updated queue
            updated_queue = queue_manager.get_queue()

            # Broadcast queue update
            await connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "reordered",
                    "queue_size": len(updated_queue)
                }
            })

            return {
                "message": "Queue reordered successfully",
                "queue_size": len(updated_queue)
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reorder queue: {e}")

    @router.post("/api/player/queue/clear")
    async def clear_queue():
        """
        Clear the entire playback queue.

        Returns:
            dict: Success message

        Raises:
            HTTPException: If player not available or operation fails
        """
        player_state_manager = get_player_state_manager()
        audio_player = get_audio_player()

        if not player_state_manager:
            raise HTTPException(status_code=503, detail="Player not available")
        if not audio_player or not hasattr(audio_player, 'queue_manager'):
            raise HTTPException(status_code=503, detail="Queue manager not available")

        try:
            queue_manager = audio_player.queue_manager

            # Clear queue
            queue_manager.clear()

            # Stop playback
            if hasattr(audio_player, 'stop'):
                audio_player.stop()

            # Update player state
            await player_state_manager.set_playing(False)
            await player_state_manager.set_track(None, None)

            # Broadcast queue update
            await connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "cleared",
                    "queue_size": 0
                }
            })

            return {"message": "Queue cleared successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to clear queue: {e}")

    @router.post("/api/player/queue/add-track")
    async def add_track_to_queue(request: AddTrackToQueueRequest):
        """
        Add a track to queue at specific position (for drag-and-drop).

        Args:
            request: Track ID and optional position

        Returns:
            dict: Success message

        Raises:
            HTTPException: If player/library not available or track not found
        """
        player_state_manager = get_player_state_manager()
        library_manager = get_library_manager()
        audio_player = get_audio_player()

        if not player_state_manager:
            raise HTTPException(status_code=503, detail="Player not available")
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")
        if not audio_player or not hasattr(audio_player, 'queue_manager'):
            raise HTTPException(status_code=503, detail="Queue manager not available")

        try:
            # Get track from library
            track = library_manager.tracks.get_by_id(request.track_id)
            if not track:
                raise HTTPException(status_code=404, detail="Track not found")

            queue_manager = audio_player.queue_manager

            # Add to queue at position
            if request.position is not None:
                # Insert at specific position
                current_queue = queue_manager.get_queue()
                current_queue.insert(request.position, track.filepath)
                queue_manager.set_queue(current_queue, queue_manager.current_index)
            else:
                # Append to end
                queue_manager.add_to_queue(track.filepath)

            # Get updated queue for broadcasting
            updated_queue = queue_manager.get_queue()

            # Broadcast queue update
            await connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "added",
                    "track_id": request.track_id,
                    "position": request.position,
                    "queue_size": len(updated_queue)
                }
            })

            return {
                "message": "Track added to queue",
                "track_id": request.track_id,
                "position": request.position,
                "queue_size": len(updated_queue)
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add track to queue: {e}")

    @router.put("/api/player/queue/move")
    async def move_queue_track(request: MoveQueueTrackRequest):
        """
        Move a track within the queue (for drag-and-drop).

        Args:
            request: From and to indices

        Returns:
            dict: Success message

        Raises:
            HTTPException: If player not available, invalid indices, or operation fails
        """
        player_state_manager = get_player_state_manager()
        audio_player = get_audio_player()

        if not player_state_manager:
            raise HTTPException(status_code=503, detail="Player not available")
        if not audio_player or not hasattr(audio_player, 'queue_manager'):
            raise HTTPException(status_code=503, detail="Queue manager not available")

        try:
            queue_manager = audio_player.queue_manager
            current_queue = queue_manager.get_queue()

            # Validate indices
            if request.from_index < 0 or request.from_index >= len(current_queue):
                raise HTTPException(status_code=400, detail=f"Invalid from_index: {request.from_index}")
            if request.to_index < 0 or request.to_index >= len(current_queue):
                raise HTTPException(status_code=400, detail=f"Invalid to_index: {request.to_index}")

            # Move track
            track = current_queue.pop(request.from_index)
            current_queue.insert(request.to_index, track)

            # Update queue
            queue_manager.set_queue(current_queue, queue_manager.current_index)

            # Broadcast queue update
            await connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "moved",
                    "from_index": request.from_index,
                    "to_index": request.to_index,
                    "queue_size": len(current_queue)
                }
            })

            return {
                "message": "Track moved successfully",
                "from_index": request.from_index,
                "to_index": request.to_index,
                "queue_size": len(current_queue)
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to move track: {e}")

    @router.post("/api/player/queue/shuffle")
    async def shuffle_queue():
        """
        Shuffle the playback queue (keeps current track in place).

        Returns:
            dict: Success message and queue size

        Raises:
            HTTPException: If player not available or operation fails
        """
        player_state_manager = get_player_state_manager()
        audio_player = get_audio_player()

        if not player_state_manager:
            raise HTTPException(status_code=503, detail="Player not available")
        if not audio_player or not hasattr(audio_player, 'queue_manager'):
            raise HTTPException(status_code=503, detail="Queue manager not available")

        try:
            queue_manager = audio_player.queue_manager

            # Shuffle queue
            queue_manager.shuffle()

            # Get updated queue
            updated_queue = queue_manager.get_queue()

            # Broadcast queue update
            await connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "shuffled",
                    "queue_size": len(updated_queue)
                }
            })

            return {
                "message": "Queue shuffled successfully",
                "queue_size": len(updated_queue)
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to shuffle queue: {e}")

    @router.post("/api/player/next")
    async def next_track():
        """
        Skip to next track.

        Returns:
            dict: Success message

        Raises:
            HTTPException: If audio player not available or operation fails
        """
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            if hasattr(audio_player, 'next_track'):
                success = audio_player.next_track()
                if success:
                    await connection_manager.broadcast({
                        "type": "track_changed",
                        "data": {"action": "next"}
                    })
                    return {"message": "Skipped to next track"}
                else:
                    return {"message": "No next track available"}
            else:
                return {"message": "Next track function not available"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to skip track: {e}")

    @router.post("/api/player/previous")
    async def previous_track():
        """
        Skip to previous track.

        Returns:
            dict: Success message

        Raises:
            HTTPException: If audio player not available or operation fails
        """
        audio_player = get_audio_player()
        if not audio_player:
            raise HTTPException(status_code=503, detail="Audio player not available")

        try:
            if hasattr(audio_player, 'previous_track'):
                success = audio_player.previous_track()
                if success:
                    await connection_manager.broadcast({
                        "type": "track_changed",
                        "data": {"action": "previous"}
                    })
                    return {"message": "Skipped to previous track"}
                else:
                    return {"message": "No previous track available"}
            else:
                return {"message": "Previous track function not available"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to skip track: {e}")

    return router
