"""
Playlist list / read / create / update / delete handlers (split from playlists.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from fastapi import Depends, Path, Query
from typing import Annotated, Any
from websocket.outbound_messages import broadcast_typed
import asyncio

from .dependencies import with_error_handling
from .errors import BadRequestError, NotFoundError
from .pagination import PaginationParams, compute_has_more
from .playlists_deps import _get_connection_manager, _get_repos
from .playlists_models import CreatePlaylistRequest, UpdatePlaylistRequest
from .serializers import serialize_playlist, serialize_playlists


@with_error_handling("get playlists")
async def get_playlists(
    limit: int = Query(PaginationParams.DEFAULT_LIMIT, ge=PaginationParams.MIN_LIMIT, le=PaginationParams.MAX_LIMIT, description="Number of playlists to return"),
    offset: int = Query(PaginationParams.DEFAULT_OFFSET, ge=PaginationParams.MIN_OFFSET, description="Number of playlists to skip"),
    repos: Any = Depends(_get_repos),
) -> dict[str, Any]:
    """
    Get a paginated list of playlists.

    Args:
        limit: Maximum number of playlists to return (1-200)
        offset: Number of playlists to skip

    Returns:
        dict: Page of playlists plus total/offset/limit/has_more

    Raises:
        HTTPException: If the library is not available or query fails

    Note:
        #4554: this endpoint previously accepted no query parameters and
        returned every playlist with every one of its tracks eagerly
        loaded, so it was an unbounded read of the whole playlist-to-track
        association table. It now matches the limit/offset convention (and
        the 200 cap) used by /api/albums, /api/artists and
        /api/library/tracks, and `total` is a real COUNT rather than the
        length of the page.
    """
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


@with_error_handling("get playlist")
async def get_playlist(
    playlist_id: Annotated[int, Path(ge=1)],
    repos: Any = Depends(_get_repos),
) -> dict[str, Any]:
    """
    Get playlist by ID with all tracks.

    Args:
        playlist_id: Playlist ID

    Returns:
        dict: Playlist data with full track details

    Raises:
        HTTPException: If the library is not available or playlist not found
    """
    playlist = await asyncio.to_thread(repos.playlists.get_by_id, playlist_id)
    if not playlist:
        raise NotFoundError("Playlist")

    playlist_dict = serialize_playlist(playlist)
    # Add full track details
    playlist_dict['tracks'] = [track.to_dict() for track in playlist.tracks]

    return playlist_dict


@with_error_handling("create playlist")
async def create_playlist(
    request: CreatePlaylistRequest,
    repos: Any = Depends(_get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """
    Create a new playlist.

    Args:
        request: Playlist creation data (name, description, track_ids)

    Returns:
        dict: Success message and created playlist data

    Raises:
        HTTPException: If the library is not available or creation fails
    """
    playlist = await asyncio.to_thread(
        repos.playlists.create,
        name=request.name,
        description=request.description,
        track_ids=request.track_ids if request.track_ids else None
    )

    if not playlist:
        raise BadRequestError("Failed to create playlist")

    # Broadcast playlist created event
    await broadcast_typed(
        connection_manager,
        "playlist_created",
        {
            "playlist_id": playlist.id,
            "name": playlist.name,
        },
    )

    return {
        "message": f"Playlist '{request.name}' created",
        "playlist": serialize_playlist(playlist)
    }


@with_error_handling("update playlist")
async def update_playlist(
    playlist_id: Annotated[int, Path(ge=1)],
    request: UpdatePlaylistRequest,
    repos: Any = Depends(_get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """
    Update playlist name or description.

    Args:
        playlist_id: Playlist ID
        request: Update data (name and/or description)

    Returns:
        dict: Success message

    Raises:
        HTTPException: If the library is not available, no data provided, or update fails
    """
    # Build update data dictionary
    update_data = {}
    if request.name is not None:
        update_data['name'] = request.name
    if request.description is not None:
        update_data['description'] = request.description

    if not update_data:
        raise BadRequestError("No update data provided")

    success = await asyncio.to_thread(repos.playlists.update, playlist_id, update_data)

    if not success:
        raise NotFoundError("Playlist", detail="Playlist not found or update failed")

    # Broadcast playlist updated event
    await broadcast_typed(
        connection_manager,
        "playlist_updated",
        {
            "playlist_id": playlist_id,
            "action": "renamed",
        },
    )

    return {"message": "Playlist updated successfully"}


@with_error_handling("delete playlist")
async def delete_playlist(
    playlist_id: Annotated[int, Path(ge=1)],
    repos: Any = Depends(_get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """
    Delete a playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        dict: Success message

    Raises:
        HTTPException: If the library is not available or playlist not found
    """
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
    await broadcast_typed(
        connection_manager,
        "playlist_deleted",
        {"playlist_id": playlist_id},
    )

    return {"message": "Playlist deleted successfully"}
