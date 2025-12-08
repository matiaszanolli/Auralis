# -*- coding: utf-8 -*-

"""
Artists API Router
~~~~~~~~~~~~~~~~~~

REST API endpoints for artist browsing and management

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Optional, Callable, Any, List, cast
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .dependencies import require_library_manager
from .errors import NotFoundError, handle_query_error


# Response models
class ArtistResponse(BaseModel):
    """Artist information response"""
    id: int
    name: str
    album_count: int
    track_count: int
    genres: Optional[list[str]] = None


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
    track_number: Optional[int] = None
    disc_number: Optional[int] = None


class AlbumInArtist(BaseModel):
    """Album information in artist context"""
    id: int
    title: str
    year: Optional[int] = None
    track_count: int
    total_duration: float


class ArtistDetailResponse(BaseModel):
    """Detailed artist information with albums and tracks"""
    artist_id: int
    artist_name: str
    albums: list[AlbumInArtist]
    total_albums: int
    total_tracks: int


class ArtistTracksResponse(BaseModel):
    """Artist's tracks response"""
    artist_id: int
    artist_name: str
    tracks: list[TrackInArtist]
    total_tracks: int


def create_artists_router(get_library_manager: Callable[[], Any]) -> APIRouter:
    """Create and configure the artists API router

    Args:
        get_library_manager: Callable that returns the LibraryManager instance

    Returns:
        Configured APIRouter instance
    """
    router = APIRouter()

    @router.get("/api/artists", response_model=ArtistsListResponse)
    async def get_artists(
        limit: int = Query(50, ge=1, le=200, description="Number of artists to return"),
        offset: int = Query(0, ge=0, description="Number of artists to skip"),
        search: Optional[str] = Query(None, description="Search query for artist name"),
        order_by: str = Query('name', description="Sort by: name, album_count, track_count")
    ) -> ArtistsListResponse:
        """Get paginated list of artists

        Returns artists with album and track counts, supporting pagination,
        search, and multiple sort options.
        """
        try:
            manager = require_library_manager(get_library_manager)

            if search:
                # Search artists by name (now returns tuple with count)
                artists, total = manager.artists.search(search, limit=limit, offset=offset)
            else:
                # Get paginated artists
                artists, total = manager.artists.get_all(
                    limit=limit,
                    offset=offset,
                    order_by=order_by
                )

            # Transform to response format
            artist_responses = []
            for artist in artists:
                # Get unique genres from artist's tracks
                # Note: Track has many-to-many relationship with genres
                genres = set()
                for track in artist.tracks:
                    if hasattr(track, 'genres') and track.genres:
                        for genre in track.genres:
                            if hasattr(genre, 'name'):
                                genres.add(genre.name)

                genres_list = list(genres) if genres else None

                artist_responses.append(ArtistResponse(
                    id=cast(int, artist.id),
                    name=cast(str, artist.name),
                    album_count=len(artist.albums) if artist.albums else 0,
                    track_count=len(artist.tracks) if artist.tracks else 0,
                    genres=genres_list
                ))

            has_more = (offset + limit) < total

            return ArtistsListResponse(
                artists=artist_responses,
                total=total,
                offset=offset,
                limit=limit,
                has_more=has_more
            )

        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("fetch artists", e)

    @router.get("/api/artists/{artist_id}", response_model=ArtistDetailResponse)
    async def get_artist(artist_id: int) -> ArtistDetailResponse:
        """Get detailed information about a specific artist

        Returns artist information with all their albums.
        """
        try:
            manager = require_library_manager(get_library_manager)
            artist = manager.artists.get_by_id(artist_id)

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
                artist_id=cast(int, artist.id),
                artist_name=cast(str, artist.name),
                albums=albums,
                total_albums=len(albums),
                total_tracks=len(artist.tracks) if artist.tracks else 0
            )

        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("fetch artist", e)

    @router.get("/api/artists/{artist_id}/tracks", response_model=ArtistTracksResponse)
    async def get_artist_tracks(artist_id: int) -> ArtistTracksResponse:
        """Get all tracks for a specific artist

        Returns all tracks by the artist, sorted by album and track number.
        """
        try:
            manager = require_library_manager(get_library_manager)
            artist = manager.artists.get_by_id(artist_id)

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
                    disc_number=track.disc_number
                ))

            # Sort tracks by album, disc number, then track number
            tracks.sort(key=lambda t: (
                t.album,
                t.disc_number or 1,
                t.track_number or 999
            ))

            return ArtistTracksResponse(
                artist_id=cast(int, artist.id),
                artist_name=cast(str, artist.name),
                tracks=tracks,
                total_tracks=len(tracks)
            )

        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("fetch artist tracks", e)

    return router
