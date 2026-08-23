"""
Library Tracks Router
~~~~~~~~~~~~~~~~~~~~~

Track-domain endpoints: listing, pagination, favorites, and lyrics.

Endpoints:
- GET  /api/library/tracks              - Paginated track listing with search
- GET  /api/library/tracks/favorites    - Paginated favorites listing
- GET  /api/library/tracks/{track_id}   - Single track by ID
- POST /api/library/tracks/{track_id}/favorite   - Mark as favorite
- DELETE /api/library/tracks/{track_id}/favorite - Remove from favorites
- GET  /api/library/tracks/{track_id}/lyrics     - Track lyrics

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Annotated, Any, Literal
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from schemas import TrackListResponse, TrackResponse

from .dependencies import require_repository_factory
from .errors import NotFoundError, handle_query_error
from .pagination import PaginationParams, compute_has_more
from .serializers import serialize_tracks

logger = logging.getLogger(__name__)


class TrackFavoriteResponse(BaseModel):
    """Result of toggling a track's favorite flag."""
    message: str = Field(description="Human-readable confirmation")
    track_id: int = Field(description="Track that was updated")
    favorite: bool = Field(description="Favorite state after the update")


class TrackLyricsResponse(BaseModel):
    """Lyrics for a track, from the database or extracted from the file.

    All three fields are null-able: a track with no lyrics anywhere returns
    `{track_id, lyrics: null, format: null}` rather than a 404.
    """
    track_id: int = Field(description="Track database ID")
    lyrics: str | None = Field(default=None, description="Lyrics text, or null when unavailable")
    format: Literal["lrc", "plain"] | None = Field(
        default=None,
        description="'lrc' when timestamped, 'plain' otherwise, null when no lyrics",
    )


def create_tracks_router(
    get_repository_factory: Callable[[], Any],
) -> APIRouter:
    """Factory: track-domain routes."""
    router = APIRouter(tags=["library"])

    @router.get("/api/library/tracks", response_model=TrackListResponse)
    async def get_tracks(
        limit: int = Query(PaginationParams.DEFAULT_LIMIT, ge=PaginationParams.MIN_LIMIT, le=PaginationParams.MAX_LIMIT),
        offset: int = Query(PaginationParams.DEFAULT_OFFSET, ge=PaginationParams.MIN_OFFSET),
        search: str | None = None,
        # #2727: Literal type makes FastAPI reject unknown values with
        # 422 at the route layer instead of silently coercing to 'title'.
        order_by: Literal[
            'title', 'created_at', 'play_count',
            'duration', 'year', 'last_played'
        ] = 'created_at',
    ) -> dict[str, Any]:
        """Get tracks from library with optional search and pagination."""
        try:
            repos = require_repository_factory(get_repository_factory)
            if search:
                tracks, total = await asyncio.to_thread(
                    repos.tracks.search, search, limit=limit, offset=offset, order_by=order_by
                )
            else:
                tracks, total = await asyncio.to_thread(repos.tracks.get_all, limit=limit, offset=offset, order_by=order_by)
            has_more = compute_has_more(offset, len(tracks), total)
            return {
                "tracks": serialize_tracks(tracks),
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get tracks", e)

    @router.get("/api/library/tracks/favorites", response_model=TrackListResponse)
    async def get_favorite_tracks(
        limit: int = Query(PaginationParams.DEFAULT_LIMIT, ge=PaginationParams.MIN_LIMIT, le=PaginationParams.MAX_LIMIT),
        offset: int = Query(PaginationParams.DEFAULT_OFFSET, ge=PaginationParams.MIN_OFFSET),
    ) -> dict[str, Any]:
        """Get all favorite tracks with pagination."""
        try:
            repos = require_repository_factory(get_repository_factory)
            tracks, total = await asyncio.to_thread(repos.tracks.get_favorites, limit=limit, offset=offset)
            has_more = compute_has_more(offset, len(tracks), total)
            return {
                "tracks": serialize_tracks(tracks),
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get favorite tracks", e)

    @router.get("/api/library/tracks/{track_id}", response_model=TrackResponse)
    async def get_track(track_id: Annotated[int, Path(ge=1)]) -> dict[str, Any]:
        """Get a single track by ID."""
        try:
            repos = require_repository_factory(get_repository_factory)
            track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)
            if not track:
                raise NotFoundError("Track", track_id)
            return serialize_tracks([track])[0]
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get track", e)

    @router.post("/api/library/tracks/{track_id}/favorite", response_model=TrackFavoriteResponse)
    async def set_track_favorite(track_id: Annotated[int, Path(ge=1)]) -> dict[str, Any]:
        """Mark track as favorite."""
        try:
            repos = require_repository_factory(get_repository_factory)
            found = await asyncio.to_thread(repos.tracks.set_favorite, track_id, True)
            if not found:
                raise NotFoundError("Track", track_id)
            logger.info(f"Track {track_id} marked as favorite")
            return {"message": "Track marked as favorite", "track_id": track_id, "favorite": True}
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("set track favorite", e)

    @router.delete("/api/library/tracks/{track_id}/favorite", response_model=TrackFavoriteResponse)
    async def remove_track_favorite(track_id: Annotated[int, Path(ge=1)]) -> dict[str, Any]:
        """Remove track from favorites."""
        try:
            repos = require_repository_factory(get_repository_factory)
            found = await asyncio.to_thread(repos.tracks.set_favorite, track_id, False)
            if not found:
                raise NotFoundError("Track", track_id)
            logger.info(f"Track {track_id} removed from favorites")
            return {"message": "Track removed from favorites", "track_id": track_id, "favorite": False}
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("remove track favorite", e)

    @router.get("/api/library/tracks/{track_id}/lyrics", response_model=TrackLyricsResponse)
    async def get_track_lyrics(track_id: Annotated[int, Path(ge=1)]) -> dict[str, Any]:
        """Get lyrics for a track, from DB or extracted from file."""
        try:
            repos = require_repository_factory(get_repository_factory)
            track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)
            if not track:
                raise NotFoundError("Track", track_id)

            if track.lyrics:
                return {
                    "track_id": track_id,
                    "lyrics": track.lyrics,
                    "format": "lrc" if "[" in track.lyrics and "]" in track.lyrics else "plain",
                }

            # Try to extract from file
            try:
                from security.path_security import validate_file_path
                validate_file_path(str(track.filepath))
                import mutagen
                audio_file = await asyncio.to_thread(mutagen.File, track.filepath)
                lyrics_text = None

                if audio_file:
                    from mutagen.mp4 import MP4
                    if isinstance(audio_file, MP4):
                        # MP4/M4A: iTunes '©lyr' atom — must check before Vorbis branch
                        # because MP4Tags implements .get() and would match incorrectly
                        # (fixes #2383).
                        try:
                            lyrics_text = audio_file.get('\xa9lyr', [None])[0]
                        except Exception as _lyr_exc:
                            logger.debug("Failed to read MP4 lyrics tag: %s", _lyr_exc)
                    elif hasattr(audio_file, 'tags') and audio_file.tags:
                        if 'USLT::eng' in audio_file.tags:
                            lyrics_text = str(audio_file.tags['USLT::eng'])
                        elif 'USLT' in audio_file.tags:
                            lyrics_text = str(audio_file.tags['USLT'])
                        elif 'LYRICS' in audio_file.tags:
                            lyrics_text = str(audio_file.tags['LYRICS'])
                    elif hasattr(audio_file, 'get'):
                        lyrics_text = audio_file.get('LYRICS', [None])[0] or audio_file.get('UNSYNCEDLYRICS', [None])[0]

                if lyrics_text:
                    result = {
                        "track_id": track_id,
                        "lyrics": lyrics_text,
                        "format": "lrc" if "[" in lyrics_text and "]" in lyrics_text else "plain",
                    }
                    try:
                        await asyncio.to_thread(repos.tracks.update_metadata, track_id, lyrics=lyrics_text)
                    except Exception as persist_exc:
                        # Extraction already succeeded — a persistence failure should not
                        # discard a result already computed in this request (#4730).
                        logger.error(f"Failed to persist extracted lyrics for track {track_id}: {persist_exc}")
                    return result
            except Exception as e:
                logger.error(f"Failed to extract lyrics from file: {e}")

            return {"track_id": track_id, "lyrics": None, "format": None}

        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get track lyrics", e)

    return router
