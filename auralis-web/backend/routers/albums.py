"""
Albums Router
~~~~~~~~~~~~~

REST API endpoints for album browsing and management

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)


def create_albums_router(get_library_manager):
    """
    Create albums router with dependency injection.

    Args:
        get_library_manager: Function that returns LibraryManager instance

    Returns:
        Configured APIRouter
    """
    router = APIRouter()

    @router.get("/api/albums")
    async def get_albums(
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        order_by: str = 'title'
    ):
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
            HTTPException: If library manager not available or query fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            # Get albums with pagination
            if search:
                albums = library_manager.albums.search(search, limit=limit, offset=offset)
                # For search, we don't have total count yet, so estimate
                total = len(albums) + offset
                has_more = len(albums) >= limit
            else:
                albums, total = library_manager.albums.get_all(limit=limit, offset=offset, order_by=order_by)
                has_more = (offset + len(albums)) < total

            # Convert to dicts for JSON serialization
            albums_data = []
            for album in albums:
                if hasattr(album, 'to_dict'):
                    album_dict = album.to_dict()
                    albums_data.append(album_dict)
                else:
                    albums_data.append({
                        'id': getattr(album, 'id', None),
                        'title': getattr(album, 'title', 'Unknown Album'),
                        'artist': getattr(album.artist, 'name', 'Unknown Artist') if hasattr(album, 'artist') and album.artist else 'Unknown Artist',
                        'year': getattr(album, 'year', None),
                        'artwork_path': getattr(album, 'artwork_path', None),
                        'track_count': len(album.tracks) if hasattr(album, 'tracks') else 0
                    })

            return {
                "albums": albums_data,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more
            }
        except Exception as e:
            logger.error(f"Failed to get albums: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get albums: {e}")

    @router.get("/api/albums/{album_id}")
    async def get_album(album_id: int):
        """
        Get album details by ID.

        Args:
            album_id: Album ID

        Returns:
            dict: Album object with full details

        Raises:
            HTTPException: If album not found or query fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            album = library_manager.albums.get_by_id(album_id)

            if not album:
                raise HTTPException(status_code=404, detail=f"Album {album_id} not found")

            # Convert to dict
            if hasattr(album, 'to_dict'):
                return album.to_dict()
            else:
                return {
                    'id': album.id,
                    'title': album.title,
                    'artist': album.artist.name if album.artist else 'Unknown Artist',
                    'year': album.year,
                    'artwork_path': album.artwork_path,
                    'track_count': len(album.tracks) if hasattr(album, 'tracks') else 0
                }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get album {album_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get album: {e}")

    @router.get("/api/albums/{album_id}/tracks")
    async def get_album_tracks(album_id: int):
        """
        Get all tracks for a specific album.

        Args:
            album_id: Album ID

        Returns:
            dict: List of tracks with album info

        Raises:
            HTTPException: If album not found or query fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            album = library_manager.albums.get_by_id(album_id)

            if not album:
                raise HTTPException(status_code=404, detail=f"Album {album_id} not found")

            # Convert tracks to dicts
            tracks_data = []
            for track in album.tracks:
                if hasattr(track, 'to_dict'):
                    tracks_data.append(track.to_dict())
                else:
                    tracks_data.append({
                        'id': track.id,
                        'title': track.title,
                        'duration': track.duration,
                        'track_number': track.track_number,
                        'disc_number': track.disc_number,
                    })

            # Sort by disc and track number
            tracks_data.sort(key=lambda t: (t.get('disc_number', 1) or 1, t.get('track_number', 0) or 0))

            return {
                "album_id": album_id,
                "album_title": album.title,
                "artist": album.artist.name if album.artist else 'Unknown Artist',
                "year": album.year,
                "artwork_path": album.artwork_path,
                "tracks": tracks_data,
                "total_tracks": len(tracks_data)
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get tracks for album {album_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get album tracks: {e}")

    return router
