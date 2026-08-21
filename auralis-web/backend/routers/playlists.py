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

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from schemas import (
    MAX_TRACK_ID_LIST,
    PlaylistResponse,
    QueueIndex,
    TrackId,
    TrackIdList,
    TrackResponse,
)

from .dependencies import require_repository_factory, with_error_handling
from .errors import NotFoundError
from .pagination import PaginationParams, compute_has_more
from .serializers import serialize_playlist, serialize_playlists

router = APIRouter(tags=["playlists"])


#: Playlist names and descriptions are free text but not unbounded — a name is
#: a label, not a payload, and the column behind it is a plain String.
MAX_PLAYLIST_NAME = 255
MAX_PLAYLIST_DESCRIPTION = 4096


class CreatePlaylistRequest(BaseModel):
    """Request model for creating a playlist"""
    name: str = Field(min_length=1, max_length=MAX_PLAYLIST_NAME)
    description: str = Field(default="", max_length=MAX_PLAYLIST_DESCRIPTION)
    track_ids: TrackIdList = []


class UpdatePlaylistRequest(BaseModel):
    """Request model for updating a playlist"""
    name: str | None = Field(default=None, min_length=1, max_length=MAX_PLAYLIST_NAME)
    description: str | None = Field(default=None, max_length=MAX_PLAYLIST_DESCRIPTION)


class AddTracksRequest(BaseModel):
    """Request model for adding tracks to playlist"""
    track_ids: TrackIdList


class AddTrackRequest(BaseModel):
    """Request model for adding a single track at an explicit position (#4658).

    Distinct from :class:`AddTracksRequest`: the batch route assigns positions
    by appending, which cannot express "drop this track at index N" — the
    operation drag-and-drop actually performs.
    """
    track_id: TrackId
    position: QueueIndex | None = None


class ReorderTrackRequest(BaseModel):
    """Request model for reordering a track within a playlist (#4658)."""
    from_index: QueueIndex
    to_index: QueueIndex


class PlaylistListResponse(BaseModel):
    """Paginated playlist listing."""
    playlists: list[PlaylistResponse] = Field(default_factory=list, description="Playlists in this page")
    total: int = Field(description="Total playlists in the library")
    limit: int = Field(description="Requested page size")
    offset: int = Field(description="Number of playlists skipped")
    has_more: bool = Field(description="True when further pages exist")


class PlaylistDetailResponse(PlaylistResponse):
    """A single playlist with its full track list.

    Extends :class:`PlaylistResponse` rather than redeclaring it, so the
    detail route cannot drift from the listing shape. `tracks` comes from
    `Track.to_dict()` directly here, not `serialize_tracks`.
    """
    tracks: list[TrackResponse] = Field(
        default_factory=list,
        description="Tracks in playlist order (association-table `position`)",
    )


class PlaylistMessageResponse(BaseModel):
    """Bare confirmation returned by the mutating playlist routes."""
    message: str = Field(description="Human-readable confirmation")


class CreatePlaylistResponse(BaseModel):
    """Result of creating a playlist."""
    message: str = Field(description="Human-readable confirmation")
    playlist: PlaylistResponse = Field(description="The newly created playlist")


class AddTracksResponse(BaseModel):
    """Result of a batch track add."""
    message: str = Field(description="Human-readable confirmation")
    added_count: int = Field(description="Number of tracks actually added")


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

    @router.get("/api/playlists", response_model=PlaylistListResponse)
    @with_error_handling("get playlists")
    async def get_playlists(
        limit: int = Query(PaginationParams.DEFAULT_LIMIT, ge=PaginationParams.MIN_LIMIT, le=PaginationParams.MAX_LIMIT, description="Number of playlists to return"),
        offset: int = Query(PaginationParams.DEFAULT_OFFSET, ge=PaginationParams.MIN_OFFSET, description="Number of playlists to skip"),
    ) -> dict[str, Any]:
        """
        Get a paginated list of playlists.

        Args:
            limit: Maximum number of playlists to return (1-200)
            offset: Number of playlists to skip

        Returns:
            dict: Page of playlists plus total/offset/limit/has_more

        Raises:
            HTTPException: If library manager/factory not available or query fails

        Note:
            #4554: this endpoint previously accepted no query parameters and
            returned every playlist with every one of its tracks eagerly
            loaded, so it was an unbounded read of the whole playlist-to-track
            association table. It now matches the limit/offset convention (and
            the 200 cap) used by /api/albums, /api/artists and
            /api/library/tracks, and `total` is a real COUNT rather than the
            length of the page.
        """
        repos = require_repository_factory(get_repository_factory)
        playlists, total = await asyncio.to_thread(
            repos.playlists.get_all, limit=limit, offset=offset
        )
        serialized = serialize_playlists(playlists)
        return {
            "playlists": serialized,
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": compute_has_more(offset, len(serialized), total),
        }

    @router.get("/api/playlists/{playlist_id}", response_model=PlaylistDetailResponse)
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

    @router.post("/api/playlists", response_model=CreatePlaylistResponse)
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

    @router.put("/api/playlists/{playlist_id}", response_model=PlaylistMessageResponse)
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

    @router.delete("/api/playlists/{playlist_id}", response_model=PlaylistMessageResponse)
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
        # Idempotent DELETE per RFC 7231 §4.3.5 — a repeat call after a
        # successful delete should NOT 404 (#4734, matching the
        # routers/artwork.py precedent from #3563). Only 404 when the
        # playlist itself doesn't exist; if `delete()` still returns False
        # (e.g. a concurrent delete raced us between the check and the
        # call) that's also success from the client's idempotency
        # perspective.
        playlist = await asyncio.to_thread(repos.playlists.get_by_id, playlist_id)
        if playlist is None:
            raise NotFoundError("Playlist")
        await asyncio.to_thread(repos.playlists.delete, playlist_id)

        # Broadcast playlist deleted event
        await connection_manager.broadcast({
            "type": "playlist_deleted",
            "data": {
                "playlist_id": playlist_id
            }
        })

        return {"message": "Playlist deleted successfully"}

    @router.post("/api/playlists/{playlist_id}/tracks", response_model=AddTracksResponse)
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

    @router.post("/api/playlists/{playlist_id}/tracks/add", response_model=PlaylistMessageResponse)
    @with_error_handling("add track to playlist")
    async def add_track_to_playlist(playlist_id: int, request: AddTrackRequest) -> dict[str, Any]:
        """
        Add a single track to a playlist, optionally at an explicit position.

        Complements the batch `POST /api/playlists/{id}/tracks` route, which can
        only append. Drag-and-drop needs positional insert, so this route wraps
        `PlaylistRepository.add_track()` (which has supported `position` since
        #3724/#3725). Previously the frontend called this path and got a 405
        because it pattern-matched `DELETE .../tracks/{track_id}` (#4658).

        Args:
            playlist_id: Playlist ID
            request: Track ID and optional 0-based insert position

        Returns:
            dict: Success message

        Raises:
            HTTPException: 400 if the track could not be added (e.g. duplicate)
        """
        repos = require_repository_factory(get_repository_factory)
        added = await asyncio.to_thread(
            repos.playlists.add_track, playlist_id, request.track_id, request.position
        )

        if not added:
            raise HTTPException(status_code=400, detail="Track was not added to playlist")

        await connection_manager.broadcast({
            "type": "playlist_updated",
            "data": {
                "playlist_id": playlist_id,
                "action": "track_added"
            }
        })

        return {"message": "Track added to playlist"}

    @router.put("/api/playlists/{playlist_id}/tracks/reorder", response_model=PlaylistMessageResponse)
    @with_error_handling("reorder playlist track")
    async def reorder_playlist_track(playlist_id: int, request: ReorderTrackRequest) -> dict[str, Any]:
        """
        Move a track within a playlist from one position to another.

        Wraps `PlaylistRepository.reorder_track()`, which has implemented this
        atomically since #3725 — only the HTTP route was missing, so every
        playlist reorder drag returned 405 (#4658).

        Args:
            playlist_id: Playlist ID
            request: 0-based source and target indices

        Returns:
            dict: Success message

        Raises:
            HTTPException: 400 if the indices are out of range for the playlist
        """
        repos = require_repository_factory(get_repository_factory)
        reordered = await asyncio.to_thread(
            repos.playlists.reorder_track, playlist_id, request.from_index, request.to_index
        )

        if not reordered:
            raise HTTPException(
                status_code=400,
                detail="Could not reorder track — index out of range for this playlist"
            )

        await connection_manager.broadcast({
            "type": "playlist_updated",
            "data": {
                "playlist_id": playlist_id,
                "action": "tracks_reordered"
            }
        })

        return {"message": "Playlist reordered"}

    @router.delete("/api/playlists/{playlist_id}/tracks/{track_id}", response_model=PlaylistMessageResponse)
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
            HTTPException: If library manager/factory not available or playlist not found
        """
        repos = require_repository_factory(get_repository_factory)
        # Idempotent DELETE per RFC 7231 §4.3.5 — a repeat call for a track
        # already removed (or never present) should NOT 404 (#4734).
        # PlaylistRepository.remove_track() already returns True
        # unconditionally on a successful DELETE regardless of rowcount
        # (idempotent by construction), but the router still needs its own
        # existence check: without one, a call against a wholly nonexistent
        # playlist_id silently "succeeds" too, matching the artwork
        # precedent's "404 only when the top-level resource is gone" rule.
        playlist = await asyncio.to_thread(repos.playlists.get_by_id, playlist_id)
        if playlist is None:
            raise NotFoundError("Playlist")
        await asyncio.to_thread(repos.playlists.remove_track, playlist_id, track_id)

        # Broadcast playlist updated event
        await connection_manager.broadcast({
            "type": "playlist_updated",
            "data": {
                "playlist_id": playlist_id,
                "action": "track_removed"
            }
        })

        return {"message": "Track removed from playlist"}

    @router.delete("/api/playlists/{playlist_id}/tracks", response_model=PlaylistMessageResponse)
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
