"""
Playlists Router
~~~~~~~~~~~~~~~~

Handles playlist CRUD operations and track management.

Endpoints:
- GET /api/playlists - Get all playlists
- GET /api/playlists/{playlist_id} - Get playlist by ID
- POST /api/playlists - Create new playlist
- PUT /api/playlists/{playlist_id} - Update playlist
- DELETE /api/playlists/{playlist_id} - Delete playlist
- POST /api/playlists/{playlist_id}/tracks - Add tracks to playlist
- DELETE /api/playlists/{playlist_id}/tracks/{track_id} - Remove track
- DELETE /api/playlists/{playlist_id}/tracks - Clear all tracks

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["playlists"])


class CreatePlaylistRequest(BaseModel):
    """Request model for creating a playlist"""
    name: str
    description: str = ""
    track_ids: List[int] = []


class UpdatePlaylistRequest(BaseModel):
    """Request model for updating a playlist"""
    name: Optional[str] = None
    description: Optional[str] = None


class AddTracksRequest(BaseModel):
    """Request model for adding tracks to playlist"""
    track_ids: List[int]


class AddTrackRequest(BaseModel):
    """Request model for adding a single track to playlist with position"""
    track_id: int
    position: Optional[int] = None  # None = append to end


class ReorderTrackRequest(BaseModel):
    """Request model for reordering track within playlist"""
    from_index: int
    to_index: int


def create_playlists_router(get_library_manager, connection_manager):
    """
    Factory function to create playlists router with dependencies.

    Args:
        get_library_manager: Callable that returns LibraryManager instance
        connection_manager: WebSocket connection manager for broadcasts

    Returns:
        APIRouter: Configured router instance
    """

    @router.get("/api/playlists")
    async def get_playlists():
        """
        Get all playlists.

        Returns:
            dict: List of playlists and total count

        Raises:
            HTTPException: If library manager not available or query fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            playlists = library_manager.playlists.get_all()
            return {
                "playlists": [p.to_dict() for p in playlists],
                "total": len(playlists)
            }
        except Exception as e:
            logger.error(f"Failed to get playlists: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get playlists: {e}")

    @router.get("/api/playlists/{playlist_id}")
    async def get_playlist(playlist_id: int):
        """
        Get playlist by ID with all tracks.

        Args:
            playlist_id: Playlist ID

        Returns:
            dict: Playlist data with full track details

        Raises:
            HTTPException: If library manager not available or playlist not found
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            playlist = library_manager.playlists.get_by_id(playlist_id)
            if not playlist:
                raise HTTPException(status_code=404, detail="Playlist not found")

            playlist_dict = playlist.to_dict()
            # Add full track details
            playlist_dict['tracks'] = [track.to_dict() for track in playlist.tracks]

            return playlist_dict
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get playlist: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get playlist: {e}")

    @router.post("/api/playlists")
    async def create_playlist(request: CreatePlaylistRequest):
        """
        Create a new playlist.

        Args:
            request: Playlist creation data (name, description, track_ids)

        Returns:
            dict: Success message and created playlist data

        Raises:
            HTTPException: If library manager not available or creation fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            playlist = library_manager.playlists.create(
                name=request.name,
                description=request.description,
                track_ids=request.track_ids if request.track_ids else None
            )

            if not playlist:
                raise HTTPException(status_code=400, detail="Failed to create playlist")

            # Broadcast playlist created event
            await connection_manager.broadcast({
                "type": "playlist_created",
                "data": {
                    "playlist_id": playlist.id,
                    "name": playlist.name
                }
            })

            return {
                "message": f"Playlist '{request.name}' created",
                "playlist": playlist.to_dict()
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create playlist: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create playlist: {e}")

    @router.put("/api/playlists/{playlist_id}")
    async def update_playlist(playlist_id: int, request: UpdatePlaylistRequest):
        """
        Update playlist name or description.

        Args:
            playlist_id: Playlist ID
            request: Update data (name and/or description)

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager not available, no data provided, or update fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            # Build update data dictionary
            update_data = {}
            if request.name is not None:
                update_data['name'] = request.name
            if request.description is not None:
                update_data['description'] = request.description

            if not update_data:
                raise HTTPException(status_code=400, detail="No update data provided")

            success = library_manager.playlists.update(playlist_id, update_data)

            if not success:
                raise HTTPException(status_code=404, detail="Playlist not found or update failed")

            # Broadcast playlist updated event
            await connection_manager.broadcast({
                "type": "playlist_updated",
                "data": {
                    "playlist_id": playlist_id,
                    "updates": update_data
                }
            })

            return {"message": "Playlist updated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update playlist: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update playlist: {e}")

    @router.delete("/api/playlists/{playlist_id}")
    async def delete_playlist(playlist_id: int):
        """
        Delete a playlist.

        Args:
            playlist_id: Playlist ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager not available or playlist not found
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            success = library_manager.playlists.delete(playlist_id)

            if not success:
                raise HTTPException(status_code=404, detail="Playlist not found")

            # Broadcast playlist deleted event
            await connection_manager.broadcast({
                "type": "playlist_deleted",
                "data": {
                    "playlist_id": playlist_id
                }
            })

            return {"message": "Playlist deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete playlist: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete playlist: {e}")

    @router.post("/api/playlists/{playlist_id}/tracks")
    async def add_tracks_to_playlist(playlist_id: int, request: AddTracksRequest):
        """
        Add tracks to playlist.

        Args:
            playlist_id: Playlist ID
            request: List of track IDs to add

        Returns:
            dict: Success message and count of added tracks

        Raises:
            HTTPException: If library manager not available or no tracks added
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            added_count = 0
            for track_id in request.track_ids:
                if library_manager.playlists.add_track(playlist_id, track_id):
                    added_count += 1

            if added_count == 0:
                raise HTTPException(status_code=400, detail="No tracks were added")

            # Broadcast playlist updated event
            await connection_manager.broadcast({
                "type": "playlist_tracks_added",
                "data": {
                    "playlist_id": playlist_id,
                    "added_count": added_count
                }
            })

            return {
                "message": f"Added {added_count} track(s) to playlist",
                "added_count": added_count
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to add tracks to playlist: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to add tracks: {e}")

    @router.delete("/api/playlists/{playlist_id}/tracks/{track_id}")
    async def remove_track_from_playlist(playlist_id: int, track_id: int):
        """
        Remove a track from playlist.

        Args:
            playlist_id: Playlist ID
            track_id: Track ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager not available or track/playlist not found
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            success = library_manager.playlists.remove_track(playlist_id, track_id)

            if not success:
                raise HTTPException(status_code=404, detail="Playlist or track not found")

            # Broadcast playlist updated event
            await connection_manager.broadcast({
                "type": "playlist_track_removed",
                "data": {
                    "playlist_id": playlist_id,
                    "track_id": track_id
                }
            })

            return {"message": "Track removed from playlist"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to remove track from playlist: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to remove track: {e}")

    @router.delete("/api/playlists/{playlist_id}/tracks")
    async def clear_playlist(playlist_id: int):
        """
        Remove all tracks from playlist.

        Args:
            playlist_id: Playlist ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager not available or playlist not found
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            success = library_manager.playlists.clear(playlist_id)

            if not success:
                raise HTTPException(status_code=404, detail="Playlist not found")

            # Broadcast playlist cleared event
            await connection_manager.broadcast({
                "type": "playlist_cleared",
                "data": {
                    "playlist_id": playlist_id
                }
            })

            return {"message": "Playlist cleared"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to clear playlist: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to clear playlist: {e}")

    @router.post("/api/playlists/{playlist_id}/tracks/add")
    async def add_track_to_playlist(playlist_id: int, request: AddTrackRequest):
        """
        Add a single track to playlist at specific position (for drag-and-drop).

        Args:
            playlist_id: Playlist ID
            request: Track ID and optional position

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager not available or track/playlist not found
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            success = library_manager.playlists.add_track(
                playlist_id,
                request.track_id,
                request.position
            )

            if not success:
                raise HTTPException(status_code=404, detail="Playlist or track not found")

            # Broadcast playlist updated event
            await connection_manager.broadcast({
                "type": "playlist_track_added",
                "data": {
                    "playlist_id": playlist_id,
                    "track_id": request.track_id,
                    "position": request.position
                }
            })

            return {
                "message": "Track added to playlist",
                "track_id": request.track_id,
                "position": request.position
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to add track to playlist: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to add track: {e}")

    @router.put("/api/playlists/{playlist_id}/tracks/reorder")
    async def reorder_playlist_track(playlist_id: int, request: ReorderTrackRequest):
        """
        Reorder track within playlist (for drag-and-drop).

        Args:
            playlist_id: Playlist ID
            request: From and to indices

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager not available, invalid indices, or playlist not found
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            success = library_manager.playlists.reorder_track(
                playlist_id,
                request.from_index,
                request.to_index
            )

            if not success:
                raise HTTPException(status_code=400, detail="Failed to reorder track (invalid indices or playlist not found)")

            # Broadcast playlist reordered event
            await connection_manager.broadcast({
                "type": "playlist_track_reordered",
                "data": {
                    "playlist_id": playlist_id,
                    "from_index": request.from_index,
                    "to_index": request.to_index
                }
            })

            return {
                "message": "Track reordered successfully",
                "from_index": request.from_index,
                "to_index": request.to_index
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to reorder track: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to reorder track: {e}")

    return router
