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

import asyncio
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .dependencies import require_repository_factory, with_error_handling
from .errors import NotFoundError
from .serializers import serialize_playlist, serialize_playlists

router = APIRouter(tags=["playlists"])


class CreatePlaylistRequest(BaseModel):
    """Request model for creating a playlist"""
    name: str
    description: str = ""
    track_ids: list[int] = []


class UpdatePlaylistRequest(BaseModel):
    """Request model for updating a playlist"""
    name: str | None = None
    description: str | None = None


class AddTracksRequest(BaseModel):
    """Request model for adding tracks to playlist"""
    track_ids: list[int]


def create_playlists_router(
    get_repository_factory: Callable[[], Any],
    connection_manager: Any
) -> APIRouter:
    """
    Factory function to create playlists router with dependencies.

    Args:
        get_repository_factory: Callable that returns RepositoryFactory instance
        connection_manager: WebSocket connection manager for broadcasts

    Returns:
        APIRouter: Configured router instance

    Note:
        Phase 6B: Fully migrated to RepositoryFactory pattern (no LibraryManager fallback)
    """

    @router.get("/api/playlists")
    @with_error_handling("get playlists")
    async def get_playlists() -> dict[str, Any]:
        """
        Get all playlists.

        Returns:
            dict: List of playlists and total count

        Raises:
            HTTPException: If library manager/factory not available or query fails
        """
        repos = require_repository_factory(get_repository_factory)
        playlists = await asyncio.to_thread(repos.playlists.get_all)
        return {
            "playlists": serialize_playlists(playlists),
            "total": len(playlists)
        }

    @router.get("/api/playlists/{playlist_id}")
    @with_error_handling("get playlist")
    async def get_playlist(playlist_id: int) -> dict[str, Any]:
        """
        Get playlist by ID with all tracks.

        Args:
            playlist_id: Playlist ID

        Returns:
            dict: Playlist data with full track details

        Raises:
            HTTPException: If library manager/factory not available or playlist not found
        """
        repos = require_repository_factory(get_repository_factory)
        playlist = await asyncio.to_thread(repos.playlists.get_by_id, playlist_id)
        if not playlist:
            raise NotFoundError("Playlist")

        playlist_dict = serialize_playlist(playlist)
        # Add full track details
        playlist_dict['tracks'] = [track.to_dict() for track in playlist.tracks]

        return playlist_dict

    @router.post("/api/playlists")
    @with_error_handling("create playlist")
    async def create_playlist(request: CreatePlaylistRequest) -> dict[str, Any]:
        """
        Create a new playlist.

        Args:
            request: Playlist creation data (name, description, track_ids)

        Returns:
            dict: Success message and created playlist data

        Raises:
            HTTPException: If library manager/factory not available or creation fails
        """
        repos = require_repository_factory(get_repository_factory)
        playlist = await asyncio.to_thread(
            repos.playlists.create,
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
            "playlist": serialize_playlist(playlist)
        }

    @router.put("/api/playlists/{playlist_id}")
    @with_error_handling("update playlist")
    async def update_playlist(playlist_id: int, request: UpdatePlaylistRequest) -> dict[str, Any]:
        """
        Update playlist name or description.

        Args:
            playlist_id: Playlist ID
            request: Update data (name and/or description)

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager/factory not available, no data provided, or update fails
        """
        repos = require_repository_factory(get_repository_factory)
        # Build update data dictionary
        update_data = {}
        if request.name is not None:
            update_data['name'] = request.name
        if request.description is not None:
            update_data['description'] = request.description

        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")

        success = await asyncio.to_thread(repos.playlists.update, playlist_id, update_data)

        if not success:
            raise NotFoundError("Playlist", detail="Playlist not found or update failed")

        # Broadcast playlist updated event
        await connection_manager.broadcast({
            "type": "playlist_updated",
            "data": {
                "playlist_id": playlist_id,
                "action": "renamed"
            }
        })

        return {"message": "Playlist updated successfully"}

    @router.delete("/api/playlists/{playlist_id}")
    @with_error_handling("delete playlist")
    async def delete_playlist(playlist_id: int) -> dict[str, Any]:
        """
        Delete a playlist.

        Args:
            playlist_id: Playlist ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager/factory not available or playlist not found
        """
        repos = require_repository_factory(get_repository_factory)
        success = await asyncio.to_thread(repos.playlists.delete, playlist_id)

        if not success:
            raise NotFoundError("Playlist")

        # Broadcast playlist deleted event
        await connection_manager.broadcast({
            "type": "playlist_deleted",
            "data": {
                "playlist_id": playlist_id
            }
        })

        return {"message": "Playlist deleted successfully"}

    @router.post("/api/playlists/{playlist_id}/tracks")
    @with_error_handling("add tracks to playlist")
    async def add_tracks_to_playlist(playlist_id: int, request: AddTracksRequest) -> dict[str, Any]:
        """
        Add tracks to playlist.

        Args:
            playlist_id: Playlist ID
            request: List of track IDs to add

        Returns:
            dict: Success message and count of added tracks

        Raises:
            HTTPException: If library manager/factory not available or no tracks added
        """
        repos = require_repository_factory(get_repository_factory)
        # Single to_thread call for all IDs — avoids N×session-open/commit
        # overhead and the frontend 5s timeout on large album imports
        # (fixes #3856; replaces N×add_track loop).
        added_count = await asyncio.to_thread(
            repos.playlists.add_tracks, playlist_id, request.track_ids
        )

        if added_count == 0:
            raise HTTPException(status_code=400, detail="No tracks were added")

        # Broadcast playlist updated event
        await connection_manager.broadcast({
            "type": "playlist_updated",
            "data": {
                "playlist_id": playlist_id,
                "action": "track_added"
            }
        })

        return {
            "message": f"Added {added_count} track(s) to playlist",
            "added_count": added_count
        }

    @router.delete("/api/playlists/{playlist_id}/tracks/{track_id}")
    @with_error_handling("remove track from playlist")
    async def remove_track_from_playlist(playlist_id: int, track_id: int) -> dict[str, Any]:
        """
        Remove a track from playlist.

        Args:
            playlist_id: Playlist ID
            track_id: Track ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager/factory not available or track/playlist not found
        """
        repos = require_repository_factory(get_repository_factory)
        success = await asyncio.to_thread(repos.playlists.remove_track, playlist_id, track_id)

        if not success:
            raise NotFoundError("Playlist", detail="Playlist or track not found")

        # Broadcast playlist updated event
        await connection_manager.broadcast({
            "type": "playlist_updated",
            "data": {
                "playlist_id": playlist_id,
                "action": "track_removed"
            }
        })

        return {"message": "Track removed from playlist"}

    @router.delete("/api/playlists/{playlist_id}/tracks")
    @with_error_handling("clear playlist")
    async def clear_playlist(playlist_id: int) -> dict[str, Any]:
        """
        Remove all tracks from playlist.

        Args:
            playlist_id: Playlist ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager/factory not available or playlist not found
        """
        repos = require_repository_factory(get_repository_factory)
        success = await asyncio.to_thread(repos.playlists.clear, playlist_id)

        if not success:
            raise NotFoundError("Playlist")

        # Broadcast playlist cleared event
        await connection_manager.broadcast({
            "type": "playlist_updated",
            "data": {
                "playlist_id": playlist_id,
                "action": "cleared"
            }
        })

        return {"message": "Playlist cleared"}

    return router
