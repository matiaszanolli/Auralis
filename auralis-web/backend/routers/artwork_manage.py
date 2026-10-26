"""
Artwork extract / delete / download handlers (split from artwork.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from fastapi import Depends
from fastapi import Path as PathParam
from typing import Annotated, Any
import asyncio

from .artwork_deps import _broadcast_artwork_updated, _get_connection_manager, _repo_deps
from .artwork_thumbnails import _purge_album_thumbnails
from .dependencies import with_error_handling
from .errors import NotFoundError


@with_error_handling("extract artwork")
async def extract_album_artwork(
    album_id: Annotated[int, PathParam(ge=1)],
    repos: Any = Depends(_repo_deps.get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """
    Extract artwork from album tracks.

    Extracts embedded artwork from the album's audio files and saves it.

    Args:
        album_id: Album ID

    Returns:
        dict: Success message and artwork URL

    Raises:
        HTTPException: If the library is not available or extraction fails
    """
    # The superseded generation's thumbnails are keyed on the OLD source
    # path, which the extract below overwrites, so read it first (#4532).
    previous = await asyncio.to_thread(repos.albums.get_by_id, album_id)
    previous_path = previous.artwork_path if previous else None

    artwork_path = await asyncio.to_thread(repos.albums.extract_and_save_artwork, album_id)

    if not artwork_path:
        raise NotFoundError("Artwork", detail="No artwork found in album tracks")

    # Purge both paths: the old one covers a move to a new file, the new one
    # covers an in-place overwrite (same path, fresh mtime — the old key
    # still sits in the cache). Thumbnails render lazily, so nothing for the
    # new generation exists yet and this cannot delete a live entry.
    await asyncio.to_thread(_purge_album_thumbnails, previous_path, artwork_path)

    # Convert filesystem path to API URL
    artwork_url = f"/api/albums/{album_id}/artwork"

    # Broadcast artwork updated event
    await _broadcast_artwork_updated(connection_manager, "extracted", album_id, artwork_url)

    return {
        "message": "Artwork extracted successfully",
        "artwork_url": artwork_url,  # API URL — consistent with artist serializer (fixes #2508)
        "album_id": album_id
    }


@with_error_handling("delete artwork")
async def delete_album_artwork(
    album_id: Annotated[int, PathParam(ge=1)],
    repos: Any = Depends(_repo_deps.get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """
    Delete album artwork.

    Args:
        album_id: Album ID

    Returns:
        dict: Success message

    Raises:
        HTTPException: If the library is not available or artwork not found
    """
    # Idempotent DELETE per RFC 7231 §4.3.5 — a repeat call after a
    # successful delete should NOT 404 (#3563 / BE-NEW-105). Only
    # 404 when the album itself doesn't exist; if artwork is
    # already gone, return success.
    album = await asyncio.to_thread(repos.albums.get_by_id, album_id)
    if album is None:
        raise NotFoundError("Album", album_id)
    # Read the source path BEFORE the row is cleared — it is the only way
    # back to the derived thumbnails, and delete_artwork discards it (#4532).
    source_path = album.artwork_path
    success = await asyncio.to_thread(repos.albums.delete_artwork, album_id)
    # If repo returns False the artwork was already absent — also
    # success from the client's idempotency perspective.

    # Drop the derived thumbnails. Runs regardless of `success` so a
    # half-finished earlier delete (row gone, cache left) still gets cleaned
    # up, and after the DB write so a purge failure cannot fail the request —
    # purge_thumbnails swallows its own OSErrors for that reason.
    await asyncio.to_thread(_purge_album_thumbnails, source_path)

    # Broadcast artwork updated event (only when something actually changed)
    if success:
        await _broadcast_artwork_updated(connection_manager, "deleted", album_id)

    return {"message": "Artwork deleted successfully", "album_id": album_id}


@with_error_handling("download artwork")
async def download_album_artwork(
    album_id: Annotated[int, PathParam(ge=1)],
    repos: Any = Depends(_repo_deps.get_repos),
    connection_manager: Any = Depends(_get_connection_manager),
) -> dict[str, Any]:
    """
    Download album artwork from online sources.

    Automatically searches and downloads artwork from MusicBrainz and iTunes.

    Args:
        album_id: Album ID

    Returns:
        dict: Success message and artwork path

    Raises:
        HTTPException: If the library is not available or download fails
    """
    # Get album using repository (includes eager loading of artist)
    album = await asyncio.to_thread(repos.albums.get_by_id, album_id)

    if not album:
        raise NotFoundError("Album")

    # Get artist name (from first track if available)
    artist_name = album.artist.name if album.artist else "Unknown Artist"
    album_name = album.title

    # Download artwork using the artwork downloader service
    from services.artwork_downloader import get_artwork_downloader
    downloader = get_artwork_downloader()

    artwork_path = await downloader.download_artwork(
        artist=artist_name,
        album=album_name,
        album_id=album_id
    )

    if not artwork_path:
        raise NotFoundError(
            "Artwork", detail=f"No artwork found online for '{album_name}' by '{artist_name}'"
        )

    # Captured before update_artwork_path replaces it, so the superseded
    # generation's thumbnails can still be located (#4532).
    previous_path = album.artwork_path

    # Save artwork path to database
    updated_album = await asyncio.to_thread(repos.albums.update_artwork_path, album_id, artwork_path)
    if not updated_album:
        raise NotFoundError("Album")

    # Same both-paths purge as the extract route above.
    await asyncio.to_thread(_purge_album_thumbnails, previous_path, artwork_path)

    # Convert filesystem path to API URL
    artwork_url = f"/api/albums/{album_id}/artwork"

    # Broadcast artwork updated event
    await _broadcast_artwork_updated(connection_manager, "downloaded", album_id, artwork_url)

    return {
        "message": "Artwork downloaded successfully",
        "artwork_url": artwork_url,  # API URL, not filesystem path
        "album_id": album_id,
        "artist": artist_name,
        "album": album_name
    }
