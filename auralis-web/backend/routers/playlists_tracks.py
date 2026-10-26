"""
Playlist membership handlers: add, reorder, remove, clear (split from playlists.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from fastapi import Depends, Path
from typing import Annotated, Any
from websocket.outbound_messages import broadcast_typed
import asyncio

from .dependencies import with_error_handling
from .errors import BadRequestError, NotFoundError
from .playlists_deps import _get_connection_manager, _repo_deps
from .playlists_models import AddTrackRequest, AddTracksRequest, ReorderTrackRequest


@with_error_handling("add tracks to playlist")
async def add_tracks_to_playlist(
    playlist_id: Annotated[int, Path(ge=1)],
    request: AddTracksRequest,
    repos: Any = Depends(_repo_deps.get_repos),
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
        HTTPException: If the library is unavailable or playlist is missing
    """
    # add_tracks() deliberately returns 0 both for a missing playlist and for
    # an idempotent all-duplicate request. Resolve existence first so only the
    # former is a 404; the latter is a successful no-op (#5263).
    playlist = await asyncio.to_thread(repos.playlists.get_by_id, playlist_id)
    if playlist is None:
        raise NotFoundError("Playlist")

    # Single to_thread call for all IDs — avoids N×session-open/commit
    # overhead and the frontend 5s timeout on large album imports
    # (fixes #3856; replaces N×add_track loop).
    added_count = await asyncio.to_thread(
        repos.playlists.add_tracks, playlist_id, request.track_ids
    )

    if added_count > 0:
        # Broadcast only when membership actually changed. Re-adding tracks
        # that are already present is successful but has no update to announce.
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
    repos: Any = Depends(_repo_deps.get_repos),
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
        raise BadRequestError("Track was not added to playlist")

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
    repos: Any = Depends(_repo_deps.get_repos),
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
        raise BadRequestError("Could not reorder track — index out of range for this playlist")

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
    repos: Any = Depends(_repo_deps.get_repos),
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
        HTTPException: If the library is not available or playlist not found
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
    repos: Any = Depends(_repo_deps.get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """
    Remove all tracks from playlist.

    Args:
        playlist_id: Playlist ID

    Returns:
        dict: Success message

    Raises:
        HTTPException: If the library is not available or playlist not found
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
