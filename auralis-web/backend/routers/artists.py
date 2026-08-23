"""
Artists API Router
~~~~~~~~~~~~~~~~~~

REST API endpoints for artist browsing and management

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
from typing import Annotated, Any, Literal, cast
from collections.abc import Callable

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel

from .dependencies import require_repository_factory, with_error_handling
from .errors import NotFoundError
from .pagination import PaginationParams, compute_has_more
from .serializers import serialize_artist


# Response models
class ArtistResponse(BaseModel):
    """Artist information response.

    Covers the union of `Artist.to_dict()` and `DEFAULT_ARTIST_FIELDS` — the
    two shapes `serialize_artist()` can return. The five fields below the
    artwork pair were missing until #3838: `response_model` filters anything
    it does not declare, so `/api/artists` was silently stripping them from
    every response with no error and no log line. Pinned by
    `tests/backend/test_response_model_coverage.py`.
    """
    id: int
    name: str
    album_count: int
    track_count: int
    genres: list[str] | None = None
    artwork_url: str | None = None  # Phase 2: Artist artwork
    artwork_source: str | None = None  # Source: 'musicbrainz', 'discogs', etc.
    normalized_name: str | None = None  # Canonical form used for duplicate detection
    total_plays: int | None = None
    avg_mastering_quality: float | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ArtistsListResponse(BaseModel):
    """Paginated artists list response"""
    artists: list[ArtistResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class TrackInArtist(BaseModel):
    """Track information in artist context"""
    id: int
    title: str
    album: str
    album_id: int
    duration: float
    track_number: int | None = None
    disc_number: int | None = None
    # #4586: every other track-returning endpoint ships `format` (it is in
    # DEFAULT_TRACK_FIELDS and Track.to_dict()); this model was the one that
    # did not, so artist-sourced queue entries lost format-aware handling.
    format: str | None = None


def _artist_genres(artist: Any, artist_data: dict[str, Any]) -> list[str] | None:
    """Distinct genre names for an artist row, or None when there are none.

    Prefers `Artist.genre_names`, which ArtistRepository's list reads populate
    from one grouped query (#5084). Falls back to walking `tracks -> genres`
    for artists that did not come from a list read — test doubles and
    detail-loaded instances — reading the collection defensively, since a
    detached instance without that eager-load raises DetachedInstanceError
    (not AttributeError, so `hasattr` would not contain it).
    """
    from_repo = artist_data.get('genres')
    if from_repo is not None:
        return list(from_repo) or None

    try:
        tracks = list(artist.tracks)
    except Exception:
        return None

    genres: set[str] = set()
    for track in tracks:
        try:
            track_genres = list(track.genres or ())
        except Exception:
            continue
        for genre in track_genres:
            name = getattr(genre, 'name', None)
            if isinstance(name, str):
                genres.add(name)
    return sorted(genres) if genres else None


def _track_format(track: Any) -> str | None:
    """Read a track's audio format defensively (#4586).

    The attribute is absent on partially-populated rows and on spec'd test
    doubles, and a bare `Mock` yields a Mock rather than a string — none of
    which should fail response validation over an informational field.
    """
    value = getattr(track, 'format', None)
    return value if isinstance(value, str) else None


class AlbumInArtist(BaseModel):
    """Album information in artist context"""
    id: int
    title: str
    year: int | None = None
    track_count: int
    total_duration: float


class ArtistDetailResponse(BaseModel):
    """Detailed artist information with albums and tracks"""
    id: int
    name: str
    albums: list[AlbumInArtist]
    total_albums: int
    total_tracks: int
    artwork_url: str | None = None  # Phase 2: Artist artwork
    artwork_source: str | None = None  # Source: 'musicbrainz', 'discogs', etc.


class ArtistTracksResponse(BaseModel):
    """Artist's tracks response"""
    id: int
    name: str
    tracks: list[TrackInArtist]
    total_tracks: int


def create_artists_router(
    get_repository_factory: Callable[[], Any]
) -> APIRouter:
    """Create and configure the artists API router

    Args:
        get_repository_factory: Callable that returns RepositoryFactory instance

    Returns:
        Configured APIRouter instance

    Note:
        Phase 6B: Fully migrated to RepositoryFactory pattern (no LibraryManager fallback)
    """
    router = APIRouter()

    @router.get("/api/artists", response_model=ArtistsListResponse)
    @with_error_handling("fetch artists")
    async def get_artists(
        limit: int = Query(PaginationParams.DEFAULT_LIMIT, ge=PaginationParams.MIN_LIMIT, le=PaginationParams.MAX_LIMIT, description="Number of artists to return"),
        offset: int = Query(PaginationParams.DEFAULT_OFFSET, ge=PaginationParams.MIN_OFFSET, description="Number of artists to skip"),
        search: str | None = Query(None, description="Search query for artist name"),
        order_by: Literal['name', 'album_count', 'track_count'] = Query(
            'name', description="Sort by: name, album_count, track_count"
        )  # fixes #3559 / BE-NEW-101 (sibling of #2727 for /api/library/tracks)
    ) -> ArtistsListResponse:
        """Get paginated list of artists

        Returns artists with album and track counts, supporting pagination,
        search, and multiple sort options.
        """
        repos = require_repository_factory(get_repository_factory)

        if search:
            # Search artists by name (now returns tuple with count)
            artists, total = await asyncio.to_thread(repos.artists.search, search, limit=limit, offset=offset)
        else:
            # Get paginated artists
            artists, total = await asyncio.to_thread(
                repos.artists.get_all,
                limit=limit,
                offset=offset,
                order_by=order_by
            )

        # Transform to response format
        artist_responses = []
        for artist in artists:
            # Genres come from the repository's single grouped query (#5084).
            # Walking artist.tracks -> track.genres here is what forced the
            # repository to hydrate every Track row on the page; it is now the
            # fallback for objects that never went through a list read (test
            # doubles, and any future caller passing a detail-loaded artist).
            artist_data = serialize_artist(artist)
            genres_list = _artist_genres(artist, artist_data)

            # #4909: counts are routed through serialize_artist() rather than
            # re-derived inline; since #5084 they originate from the
            # repository's correlated COUNT subqueries.
            # #4833: the five fields below the artwork pair were declared on
            # ArtistResponse by #3838 but never populated here, so they stayed
            # None on every response — `created_at` in particular, which the
            # frontend's Artist.dateAdded is transformed from. They all come
            # straight out of Artist.to_dict() via serialize_artist().
            artist_responses.append(ArtistResponse(
                id=cast(int, artist.id),
                name=cast(str, artist.name),
                album_count=artist_data.get('album_count', 0),
                track_count=artist_data.get('track_count', 0),
                genres=genres_list,
                artwork_url=artist.artwork_url,
                artwork_source=artist.artwork_source,
                normalized_name=artist_data.get('normalized_name'),
                total_plays=artist_data.get('total_plays'),
                avg_mastering_quality=artist_data.get('avg_mastering_quality'),
                created_at=artist_data.get('created_at'),
                updated_at=artist_data.get('updated_at'),
            ))

        has_more = compute_has_more(offset, len(artist_responses), total)

        return ArtistsListResponse(
            artists=artist_responses,
            total=total,
            offset=offset,
            limit=limit,
            has_more=has_more
        )

    @router.get("/api/artists/{artist_id}", response_model=ArtistDetailResponse)
    @with_error_handling("fetch artist")
    async def get_artist(artist_id: Annotated[int, Path(ge=1)]) -> ArtistDetailResponse:
        """Get detailed information about a specific artist

        Returns artist information with all their albums.
        """
        repos = require_repository_factory(get_repository_factory)
        artist = await asyncio.to_thread(repos.artists.get_by_id, artist_id)

        if not artist:
            raise NotFoundError("Artist", artist_id)

        # Transform albums to response format
        albums = []
        for album in (artist.albums or []):
            total_duration = sum(
                track.duration for track in album.tracks if track.duration
            ) if album.tracks else 0

            albums.append(AlbumInArtist(
                id=album.id,
                title=album.title,
                year=album.year,
                track_count=len(album.tracks) if album.tracks else 0,
                total_duration=total_duration
            ))

        # Sort albums by year (newest first), then by title
        albums.sort(key=lambda a: (-(a.year or 0), a.title))

        return ArtistDetailResponse(
            id=cast(int, artist.id),
            name=cast(str, artist.name),
            albums=albums,
            total_albums=len(albums),
            total_tracks=len(artist.tracks) if artist.tracks else 0,
            artwork_url=artist.artwork_url,
            artwork_source=artist.artwork_source,
        )

    @router.get("/api/artists/{artist_id}/tracks", response_model=ArtistTracksResponse)
    @with_error_handling("fetch artist tracks")
    async def get_artist_tracks(artist_id: Annotated[int, Path(ge=1)]) -> ArtistTracksResponse:
        """Get all tracks for a specific artist

        Returns all tracks by the artist, sorted by album and track number.
        """
        repos = require_repository_factory(get_repository_factory)
        artist = await asyncio.to_thread(repos.artists.get_by_id, artist_id)

        if not artist:
            raise NotFoundError("Artist", artist_id)

        # Transform tracks to response format
        tracks = []
        for track in (artist.tracks or []):
            tracks.append(TrackInArtist(
                id=track.id,
                title=track.title,
                album=track.album.title if track.album else "Unknown Album",
                album_id=track.album.id if track.album else 0,
                duration=track.duration or 0,
                track_number=track.track_number,
                disc_number=track.disc_number,
                format=_track_format(track),
            ))

        # Sort tracks by album, disc number, then track number
        tracks.sort(key=lambda t: (
            t.album,
            t.disc_number or 1,
            t.track_number or 999
        ))

        return ArtistTracksResponse(
            id=cast(int, artist.id),
            name=cast(str, artist.name),
            tracks=tracks,
            total_tracks=len(tracks)
        )

    return router
