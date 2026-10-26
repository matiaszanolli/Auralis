"""
Albums Router
~~~~~~~~~~~~~

REST API endpoints for album browsing and management

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Annotated, Any, Literal
from collections.abc import Callable

from fastapi import APIRouter, Depends, Path

from schemas import (
    AlbumListResponse,
    AlbumResponse,
)


from .dependencies import with_error_handling
from .errors import NotFoundError
from .pagination import limit_query, offset_query, paginated
from .serializers_library import serialize_album, serialize_albums, serialize_tracks
from .albums_models import AlbumFingerprintResponse, AlbumTracksResponse
from .albums_deps import _repo_deps
from .albums_fingerprint import (
    get_album_fingerprint,
)

logger = logging.getLogger(__name__)


def _derive_album_genre(tracks_data: list[dict[str, Any]]) -> str | None:
    """Most common genre across an album's serialized tracks (#5170).

    ``Album`` has no genre column — genre lives on ``Track`` via the
    ``track_genre`` association — so an album genre has to be derived. #4709
    removed the always-null ``genre`` key from ``serialize_album_detail`` for
    exactly this reason and called the derivation a feature rather than a bug
    fix; this is that feature, scoped to the one endpoint whose consumer
    (``useAlbumDetails`` -> ``AlbumMetadata``) renders a "Genre:" line.

    Ties are broken by first appearance in disc/track order, which is stable
    for a given album and keeps the answer deterministic. Returns ``None``
    when no track carries a genre, so the UI's ``{genre && ...}`` guard hides
    the row rather than rendering an empty one.

    Note:
        This counts each *track*, not each genre tag: a track tagged
        ``["Rock", "Blues"]`` contributes one vote to each. That matches how a
        listener would describe the album and avoids a single heavily-tagged
        track outvoting the rest.
    """
    counts: dict[str, int] = {}
    for track in tracks_data:
        for genre in track.get('genres') or []:
            if genre:
                counts[genre] = counts.get(genre, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda name: counts[name])


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_albums_router() used to be one 219-line closure: every handler below
# was nested inside it purely to reach get_repository_factory via closure
# capture, which made a handler impossible to import or call without first
# building the whole router. Handlers are now module level; they reach the
# same callable through FastAPI Depends() instead.
#
# _repo_deps (a RepositoryFactoryDeps, repo_deps.py) holds the raw callable one
# create_albums_router() call received. It is bound per router instance: a
# router-level dependency publishes it for the duration of a request, so a
# second factory call (every test that builds its own router) cannot repoint
# the live router at its stubs (#5262, #5762).
#
# A handler's Depends() default is only consulted when FastAPI itself invokes
# it for a real request; a direct unit-test call passes the repos explicitly
# as a keyword argument and never touches _repo_deps at all -- that's the
# seam #4670 asked for.
# ============================================================================


@with_error_handling("get albums")
async def get_albums(
    limit: int = limit_query(),
    offset: int = offset_query(),
    search: str | None = None,
    order_by: Literal['title', 'year', 'created_at'] = 'title',
    repos: Any = Depends(_repo_deps.get_repos),
) -> Any:
    """
    Get albums from library with optional search and pagination.

    Args:
        limit: Maximum number of albums to return (default: 50)
        offset: Number of albums to skip (default: 0)
        search: Optional search query (searches title and artist)
        order_by: Column to order by (default: 'title', options: 'title', 'year', 'created_at')

    Returns:
        dict: List of albums with pagination info including:
            - albums: List of album objects
            - total: Total number of albums in library
            - limit: Requested limit
            - offset: Current offset
            - has_more: Boolean indicating if more albums are available

    Raises:
        HTTPException: If the library is not available or query fails
    """
    # Get albums with pagination
    if search:
        albums, total = await asyncio.to_thread(repos.albums.search, search, limit=limit, offset=offset, order_by=order_by)
    else:
        albums, total = await asyncio.to_thread(repos.albums.get_all, limit=limit, offset=offset, order_by=order_by)
    return paginated("albums", serialize_albums(albums), total, offset, limit)


@with_error_handling("get album")
async def get_album(album_id: Annotated[int, Path(ge=1)], repos: Any = Depends(_repo_deps.get_repos)) -> Any:
    """
    Get album details by ID.

    Args:
        album_id: Album ID

    Returns:
        dict: Album object in the same snake_case shape as the
            ``GET /api/albums`` listing (#4679).

    Raises:
        HTTPException: If album not found or query fails
    """
    album = await asyncio.to_thread(repos.albums.get_by_id, album_id)

    if not album:
        raise NotFoundError("Album", album_id)

    # Same serializer and same response model as the listing above (#4679).
    # #4423 gave this one endpoint a camelCase shape of its own
    # (`trackCount`/`artworkUrl`/`totalDuration`) on the theory that it
    # would be consumed on the frontend's `Album` domain convention. No
    # consumer ever appeared — `useAlbumDetails.ts` reads the sibling
    # {id}/tracks endpoint — so all it produced was one entity emitted in
    # two incompatible shapes against a single declared TS contract
    # (`AlbumApiResponse`, snake_case) and a single transformer
    # (`transformAlbum`), which pointed here would have yielded an
    # all-undefined Album. The camelCase serializer and its response model
    # are gone; casing translation belongs to the frontend transformer
    # layer, as it already does for albums, artists and playlists.
    return serialize_album(album)


@with_error_handling("get album tracks")
async def get_album_tracks(album_id: Annotated[int, Path(ge=1)], repos: Any = Depends(_repo_deps.get_repos)) -> Any:
    """
    Get all tracks for a specific album.

    Args:
        album_id: Album ID

    Returns:
        dict: List of tracks with album info

    Raises:
        HTTPException: If album not found or query fails
    """
    album = await asyncio.to_thread(repos.albums.get_by_id, album_id)

    if not album:
        raise NotFoundError("Album", album_id)

    # Convert tracks to dicts
    tracks_data = serialize_tracks(album.tracks if hasattr(album, 'tracks') else [])

    # Sort by disc and track number
    tracks_data.sort(key=lambda t: (t.get('disc_number', 1) or 1, t.get('track_number', 0) or 0))

    return {
        "album_id": album_id,
        "album_title": album.title,
        "artist": album.artist.name if album.artist else None,
        "year": album.year,
        "genre": _derive_album_genre(tracks_data),
        "artwork_url": f"/api/albums/{album_id}/artwork" if album.artwork_path else None,
        "tracks": tracks_data,
        "total_tracks": len(tracks_data)
    }


def create_albums_router(
    get_repository_factory: Callable[[], Any]
) -> APIRouter:
    """
    Create albums router with dependency injection.

    Args:
        get_repository_factory: Function that returns RepositoryFactory instance

    Returns:
        Configured APIRouter

    Note:
    """
    router = APIRouter(dependencies=[Depends(_repo_deps.bind(get_repository_factory))])

    # Registration order matches the original decorator order: the literal-free
    # `/api/albums/{album_id}` must stay ahead of its `/tracks` and
    # `/fingerprint` children exactly as it did, since Starlette matches in
    # registration order.
    router.add_api_route("/api/albums", get_albums, methods=["GET"], response_model=AlbumListResponse)
    router.add_api_route("/api/albums/{album_id}", get_album, methods=["GET"], response_model=AlbumResponse)
    router.add_api_route("/api/albums/{album_id}/tracks", get_album_tracks, methods=["GET"], response_model=AlbumTracksResponse)
    router.add_api_route("/api/albums/{album_id}/fingerprint", get_album_fingerprint, methods=["GET"], response_model=AlbumFingerprintResponse)

    return router
