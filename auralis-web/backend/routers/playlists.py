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
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from schemas import (
    PlaylistResponse,
    QueueIndex,
    TrackId,
    TrackIdList,
    TrackResponse,
)
from websocket.outbound_messages import broadcast_typed

from .dependencies import require_repository_factory, with_error_handling
from .errors import NotFoundError
from .pagination import PaginationParams, compute_has_more
from .serializers import serialize_playlist, serialize_playlists

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


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_playlists_router() used to be a ~400-line closure: every handler
# below was nested inside it purely to reach get_repository_factory and
# connection_manager via closure capture, which made a handler impossible to
# import or call without first building the whole router. Handlers are now
# module level; they reach the same callables through FastAPI Depends()
# instead.
#
# _PlaylistsDeps holds the raw callables/objects the factory receives. It is
# populated exactly once, by create_playlists_router() itself -- same as the
# old closure, which only ever ran once per process (config/routes.py calls
# the factory a single time at startup; the test `client` fixture imports
# the already-built `main.app` once per process too). This is a deliberate
# simplification, not a new hazard: nothing in this codebase calls
# create_playlists_router() more than once in the same process. It does NOT
# reproduce the #4361 module-level-`APIRouter()` hazard, since the router
# instance itself is now built fresh, per call, inside the factory below.
#
# A handler's Depends() default is only consulted when FastAPI itself
# invokes it for a real request; a direct unit-test call passes the
# repos/connection_manager explicitly as a keyword argument and never
# touches _PlaylistsDeps at all -- that's the seam #4670 asked for.
# ============================================================================

class _PlaylistsDeps:
    get_repository_factory: Callable[[], Any]
    connection_manager: Any


_deps = _PlaylistsDeps()


def _get_connection_manager() -> Any:
    return _deps.connection_manager


def _get_repos() -> Any:
    """Resolve the RepositoryFactory for this request.

    Mirrors the original per-handler `require_repository_factory(
    get_repository_factory)` call exactly: the factory getter is invoked (and
    its 503-on-unavailable guard applied) once per request, not once at
    router-construction time.
    """
    return require_repository_factory(_deps.get_repository_factory)


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
        HTTPException: If library manager/factory not available or playlist not found
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
        HTTPException: If library manager/factory not available or creation fails
    """
    playlist = await asyncio.to_thread(
        repos.playlists.create,
        name=request.name,
        description=request.description,
        track_ids=request.track_ids if request.track_ids else None
    )

    if not playlist:
        raise HTTPException(status_code=400, detail="Failed to create playlist")

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
        HTTPException: If library manager/factory not available, no data provided, or update fails
    """
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
        HTTPException: If library manager/factory not available or playlist not found
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


@with_error_handling("add tracks to playlist")
async def add_tracks_to_playlist(
    playlist_id: Annotated[int, Path(ge=1)],
    request: AddTracksRequest,
    repos: Any = Depends(_get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
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
    # Single to_thread call for all IDs — avoids N×session-open/commit
    # overhead and the frontend 5s timeout on large album imports
    # (fixes #3856; replaces N×add_track loop).
    added_count = await asyncio.to_thread(
        repos.playlists.add_tracks, playlist_id, request.track_ids
    )

    if added_count == 0:
        raise HTTPException(status_code=400, detail="No tracks were added")

    # Broadcast playlist updated event
    await broadcast_typed(
        connection_manager,
        "playlist_updated",
        {
            "playlist_id": playlist_id,
            "action": "track_added",
        },
    )

    return {
        "message": f"Added {added_count} track(s) to playlist",
        "added_count": added_count
    }


@with_error_handling("add track to playlist")
async def add_track_to_playlist(
    playlist_id: Annotated[int, Path(ge=1)],
    request: AddTrackRequest,
    repos: Any = Depends(_get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
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
    added = await asyncio.to_thread(
        repos.playlists.add_track, playlist_id, request.track_id, request.position
    )

    if not added:
        raise HTTPException(status_code=400, detail="Track was not added to playlist")

    await broadcast_typed(
        connection_manager,
        "playlist_updated",
        {
            "playlist_id": playlist_id,
            "action": "track_added",
        },
    )

    return {"message": "Track added to playlist"}


@with_error_handling("reorder playlist track")
async def reorder_playlist_track(
    playlist_id: Annotated[int, Path(ge=1)],
    request: ReorderTrackRequest,
    repos: Any = Depends(_get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
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
    reordered = await asyncio.to_thread(
        repos.playlists.reorder_track, playlist_id, request.from_index, request.to_index
    )

    if not reordered:
        raise HTTPException(
            status_code=400,
            detail="Could not reorder track — index out of range for this playlist"
        )

    await broadcast_typed(
        connection_manager,
        "playlist_updated",
        {
            "playlist_id": playlist_id,
            # The frontend contract and listener both use the singular
            # `reordered`; the old plural spelling made this event a no-op.
            "action": "reordered",
        },
    )

    return {"message": "Playlist reordered"}


@with_error_handling("remove track from playlist")
async def remove_track_from_playlist(
    playlist_id: Annotated[int, Path(ge=1)],
    track_id: Annotated[int, Path(ge=1)],
    repos: Any = Depends(_get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
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
    await broadcast_typed(
        connection_manager,
        "playlist_updated",
        {
            "playlist_id": playlist_id,
            "action": "track_removed",
        },
    )

    return {"message": "Track removed from playlist"}


@with_error_handling("clear playlist")
async def clear_playlist(
    playlist_id: Annotated[int, Path(ge=1)],
    repos: Any = Depends(_get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """
    Remove all tracks from playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        dict: Success message

    Raises:
        HTTPException: If library manager/factory not available or playlist not found
    """
    success = await asyncio.to_thread(repos.playlists.clear, playlist_id)

    if not success:
        raise NotFoundError("Playlist")

    # Broadcast playlist cleared event
    await broadcast_typed(
        connection_manager,
        "playlist_updated",
        {
            "playlist_id": playlist_id,
            "action": "cleared",
        },
    )

    return {"message": "Playlist cleared"}


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
    _deps.get_repository_factory = get_repository_factory
    _deps.connection_manager = connection_manager

    router = APIRouter(tags=["playlists"])

    router.add_api_route("/api/playlists", get_playlists, methods=["GET"], response_model=PlaylistListResponse)
    router.add_api_route("/api/playlists/{playlist_id}", get_playlist, methods=["GET"], response_model=PlaylistDetailResponse)
    router.add_api_route("/api/playlists", create_playlist, methods=["POST"], response_model=CreatePlaylistResponse)
    router.add_api_route("/api/playlists/{playlist_id}", update_playlist, methods=["PUT"], response_model=PlaylistMessageResponse)
    router.add_api_route("/api/playlists/{playlist_id}", delete_playlist, methods=["DELETE"], response_model=PlaylistMessageResponse)

    # Track routes. The literal `/tracks/add` and `/tracks/reorder` paths are
    # registered before `/tracks/{track_id}`, matching the original decorator
    # order — that ordering is load-bearing for path matching (#4658).
    router.add_api_route("/api/playlists/{playlist_id}/tracks", add_tracks_to_playlist, methods=["POST"], response_model=AddTracksResponse)
    router.add_api_route("/api/playlists/{playlist_id}/tracks/add", add_track_to_playlist, methods=["POST"], response_model=PlaylistMessageResponse)
    router.add_api_route("/api/playlists/{playlist_id}/tracks/reorder", reorder_playlist_track, methods=["PUT"], response_model=PlaylistMessageResponse)
    router.add_api_route("/api/playlists/{playlist_id}/tracks/{track_id}", remove_track_from_playlist, methods=["DELETE"], response_model=PlaylistMessageResponse)
    router.add_api_route("/api/playlists/{playlist_id}/tracks", clear_playlist, methods=["DELETE"], response_model=PlaylistMessageResponse)

    return router
