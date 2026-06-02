"""
Library Router
~~~~~~~~~~~~~~

General library endpoints: statistics, reference cloud, browse (artists/albums),
and admin (reset). Track, scan, and fingerprint domains are in dedicated routers:
- routers/tracks.py             (track listing, favorites, lyrics)
- routers/library_scan.py       (directory scan with progress broadcast)
- routers/fingerprint_status.py (fingerprint status and per-track lookup)

Endpoints:
- POST /api/library/refresh-references   - Rebuild mastering reference cloud
- GET  /api/library/stats                - Library statistics
- GET  /api/library/artists              - Paginated artist list
- GET  /api/library/artists/{artist_id}  - Artist detail
- GET  /api/library/albums/{album_id}    - Album detail
- POST /api/library/reset                - Destructive full library reset

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any, cast
from collections.abc import Callable

from fastapi import APIRouter, Header, HTTPException, Query

from .dependencies import require_repository_factory
from .errors import NotFoundError, handle_query_error
from .serializers import serialize_album, serialize_artist, serialize_artists

logger = logging.getLogger(__name__)
router = APIRouter(tags=["library"])


def create_library_router(
    get_repository_factory: Callable[[], Any],
) -> APIRouter:
    """Factory: general library routes (stats, browse, reset).

    Note:
        Phase 6B: Fully migrated to RepositoryFactory pattern.
        Track / scan / fingerprint routes are registered by their own factory functions
        (create_tracks_router, create_library_scan_router, create_fingerprint_status_router).
    """

    @router.post("/api/library/refresh-references")
    async def refresh_reference_cloud() -> dict[str, Any]:
        """#3479: rebuild the mastering reference cloud from current library state.

        Clears all existing ``is_reference`` flags, scores every fingerprint
        against the seeder thresholds, and flags the top-N candidates.
        Safe to call repeatedly — the seeder is idempotent and does no audio I/O.
        """
        try:
            from auralis.learning.reference_seeder import refresh_cloud
            factory = require_repository_factory(get_repository_factory)
            cleared, selected = await asyncio.to_thread(
                refresh_cloud, factory.fingerprints
            )
            logger.info(
                f"🎯 Reference cloud refresh (manual): cleared {cleared}, selected {selected}"
            )
            return {"cleared": cleared, "selected": selected}
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("refresh reference cloud", e)

    @router.get("/api/library/stats")
    async def get_library_stats() -> dict[str, Any]:
        """Get library statistics (track count, album count, etc.)."""
        try:
            factory = require_repository_factory(get_repository_factory)
            stats = await asyncio.to_thread(factory.stats.get_library_stats)
            return cast(dict[str, Any], stats)
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get library stats", e)

    @router.get("/api/library/artists")
    async def get_artists(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        search: str | None = None,
        order_by: str = "name",
    ) -> dict[str, Any]:
        """Get paginated list of artists with optional search."""
        try:
            repos = require_repository_factory(get_repository_factory)
            limit = min(max(limit, 1), 200)
            offset = max(offset, 0)
            valid_order_by = ["name", "album_count", "track_count"]
            if order_by not in valid_order_by:
                order_by = "name"

            if search:
                artists, total = await asyncio.to_thread(repos.artists.search, search, limit=limit, offset=offset)
            else:
                artists, total = await asyncio.to_thread(repos.artists.get_all, limit=limit, offset=offset, order_by=order_by)

            has_more = (offset + len(artists)) < total
            return {
                "artists": serialize_artists(artists),
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get artists", e)

    @router.get("/api/library/artists/{artist_id}")
    async def get_artist(artist_id: int) -> dict[str, Any]:
        """Get artist details by ID with albums and tracks."""
        try:
            repos = require_repository_factory(get_repository_factory)
            artist = await asyncio.to_thread(repos.artists.get_by_id, artist_id)
            if not artist:
                raise NotFoundError("Artist", artist_id)
            return serialize_artist(artist)
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get artist", e)

    # Removed: GET /api/library/albums — dead endpoint, duplicate of GET /api/albums (fixes #2509)

    @router.get("/api/library/albums/{album_id}")
    async def get_album(album_id: int) -> dict[str, Any]:
        """Get album details by ID with tracks."""
        try:
            repos = require_repository_factory(get_repository_factory)
            album = await asyncio.to_thread(repos.albums.get_by_id, album_id)
            if not album:
                raise NotFoundError("Album", album_id)
            return serialize_album(album)
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get album", e)

    @router.post("/api/library/reset")
    async def reset_library(
        x_confirm_reset: str = Header(
            ...,
            alias="X-Confirm-Reset",
            description="Must be 'RESET' to confirm the destructive operation",
        ),
    ) -> dict[str, Any]:
        """Reset the entire library — deletes all tracks, albums, artists, genres,
        fingerprints, playlists, queue state, and play statistics.

        Requires the ``X-Confirm-Reset: RESET`` header as a safety guard
        against accidental or CSRF-triggered calls.
        """
        if x_confirm_reset != "RESET":
            raise HTTPException(
                status_code=400,
                detail="Invalid confirmation header: X-Confirm-Reset must be 'RESET'",
            )
        try:
            repos = require_repository_factory(get_repository_factory)

            # Pause background workers so in-flight DB ops don't race the
            # reset (fixes #3342).
            from analysis.fingerprint_queue import get_fingerprint_queue
            fprint_queue = get_fingerprint_queue()
            if fprint_queue:
                await fprint_queue.stop()

            def _reset_all() -> None:
                session = repos.session_factory()
                try:
                    from auralis.library.models.core import (
                        Track, Album, Artist, Genre, Playlist,
                        QueueState, QueueHistory,
                    )
                    from auralis.library.models.base import (
                        track_artist, track_genre, track_playlist,
                    )
                    from auralis.library.models.fingerprint import TrackFingerprint
                    from sqlalchemy import delete

                    session.execute(track_playlist.delete())
                    session.execute(track_genre.delete())
                    session.execute(track_artist.delete())

                    session.execute(delete(TrackFingerprint))
                    session.execute(delete(QueueHistory))
                    session.execute(delete(QueueState))
                    session.execute(delete(Track))
                    session.execute(delete(Playlist))
                    session.execute(delete(Album))
                    session.execute(delete(Artist))
                    session.execute(delete(Genre))

                    session.commit()
                    logger.info("Library reset: all tracks, albums, artists, genres, fingerprints, and playlists deleted")
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()

            await asyncio.to_thread(_reset_all)

            if fprint_queue:
                await fprint_queue.start()

            return {"message": "Library has been reset successfully"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error resetting library: {e}", exc_info=True)
            raise handle_query_error("reset library", e)

    return router
