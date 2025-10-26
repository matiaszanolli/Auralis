"""
Library Router
~~~~~~~~~~~~~~

Handles library queries for tracks, albums, artists, and statistics.

Endpoints:
- GET /api/library/stats - Get library statistics
- GET /api/library/tracks - Get tracks with optional search/pagination
- GET /api/library/tracks/favorites - Get favorite tracks
- POST /api/library/tracks/{track_id}/favorite - Mark track as favorite
- DELETE /api/library/tracks/{track_id}/favorite - Remove from favorites
- GET /api/library/tracks/{track_id}/lyrics - Get track lyrics
- GET /api/library/artists - Get all artists
- GET /api/library/artists/{artist_id} - Get artist details
- GET /api/library/albums - Get all albums
- GET /api/library/albums/{album_id} - Get album details

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["library"])


def create_library_router(get_library_manager):
    """
    Factory function to create library router with dependencies.

    Args:
        get_library_manager: Callable that returns LibraryManager instance

    Returns:
        APIRouter: Configured router instance
    """

    @router.get("/api/library/stats")
    async def get_library_stats():
        """
        Get library statistics.

        Returns:
            dict: Library statistics (track count, album count, etc.)

        Raises:
            HTTPException: If library manager not available or query fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            stats = library_manager.get_library_stats()
            return stats
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")

    @router.get("/api/library/tracks")
    async def get_tracks(
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        order_by: str = 'created_at'
    ):
        """
        Get tracks from library with optional search and pagination.

        Args:
            limit: Maximum number of tracks to return (default: 50)
            offset: Number of tracks to skip (default: 0)
            search: Optional search query
            order_by: Column to order by (default: 'created_at')

        Returns:
            dict: List of tracks with pagination info including:
                - tracks: List of track objects
                - total: Total number of tracks in library
                - limit: Requested limit
                - offset: Current offset
                - has_more: Boolean indicating if more tracks are available

        Raises:
            HTTPException: If library manager not available or query fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            # Get tracks with pagination
            if search:
                tracks = library_manager.search_tracks(search, limit=limit, offset=offset)
                # For search, we don't have total count yet, so estimate
                total = len(tracks) + offset
                has_more = len(tracks) >= limit
            else:
                tracks, total = library_manager.get_all_tracks(limit=limit, offset=offset, order_by=order_by)
                has_more = (offset + len(tracks)) < total

            # Convert to dicts for JSON serialization
            tracks_data = []
            for track in tracks:
                if hasattr(track, 'to_dict'):
                    tracks_data.append(track.to_dict())
                else:
                    tracks_data.append({
                        'id': getattr(track, 'id', None),
                        'title': getattr(track, 'title', 'Unknown'),
                        'filepath': getattr(track, 'filepath', ''),
                        'duration': getattr(track, 'duration', 0),
                        'format': getattr(track, 'format', 'Unknown')
                    })

            return {
                "tracks": tracks_data,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get tracks: {e}")

    @router.get("/api/library/tracks/favorites")
    async def get_favorite_tracks(limit: int = 50, offset: int = 0):
        """
        Get all favorite tracks with pagination.

        Args:
            limit: Maximum number of tracks to return (default: 50)
            offset: Number of tracks to skip (default: 0)

        Returns:
            dict: List of favorite tracks with pagination info

        Raises:
            HTTPException: If library manager not available or query fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            tracks = library_manager.get_favorite_tracks(limit=limit, offset=offset)

            # Convert to dicts for JSON serialization
            tracks_data = []
            for track in tracks:
                if hasattr(track, 'to_dict'):
                    tracks_data.append(track.to_dict())

            # Calculate has_more (we don't have total count for favorites, so estimate)
            has_more = len(tracks) >= limit

            return {
                "tracks": tracks_data,
                "total": len(tracks_data) + offset,
                "limit": limit,
                "offset": offset,
                "has_more": has_more
            }
        except Exception as e:
            logger.error(f"Failed to get favorite tracks: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get favorites: {e}")

    @router.post("/api/library/tracks/{track_id}/favorite")
    async def set_track_favorite(track_id: int):
        """
        Mark track as favorite.

        Args:
            track_id: Track ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager not available or operation fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            library_manager.tracks.set_favorite(track_id, True)
            logger.info(f"Track {track_id} marked as favorite")
            return {"message": "Track marked as favorite", "track_id": track_id, "favorite": True}
        except Exception as e:
            logger.error(f"Failed to set favorite: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to set favorite: {e}")

    @router.delete("/api/library/tracks/{track_id}/favorite")
    async def remove_track_favorite(track_id: int):
        """
        Remove track from favorites.

        Args:
            track_id: Track ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager not available or operation fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            library_manager.tracks.set_favorite(track_id, False)
            logger.info(f"Track {track_id} removed from favorites")
            return {"message": "Track removed from favorites", "track_id": track_id, "favorite": False}
        except Exception as e:
            logger.error(f"Failed to remove favorite: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to remove favorite: {e}")

    @router.get("/api/library/tracks/{track_id}/lyrics")
    async def get_track_lyrics(track_id: int):
        """
        Get lyrics for a track.

        Attempts to retrieve lyrics from database first, then extracts from file if needed.

        Args:
            track_id: Track ID

        Returns:
            dict: Lyrics text and format (lrc or plain), or None if not found

        Raises:
            HTTPException: If library manager not available, track not found, or query fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            track = library_manager.tracks.get_by_id(track_id)
            if not track:
                raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

            # If lyrics exist in database, return them
            if track.lyrics:
                return {
                    "track_id": track_id,
                    "lyrics": track.lyrics,
                    "format": "lrc" if "[" in track.lyrics and "]" in track.lyrics else "plain"
                }

            # If no lyrics in database, try to extract from file
            try:
                import mutagen
                audio_file = mutagen.File(track.filepath)

                lyrics_text = None

                # Try different lyrics tags
                if audio_file:
                    # ID3 tags (MP3)
                    if hasattr(audio_file, 'tags') and audio_file.tags:
                        # USLT frame (Unsynchronized lyrics)
                        if 'USLT::eng' in audio_file.tags:
                            lyrics_text = str(audio_file.tags['USLT::eng'])
                        elif 'USLT' in audio_file.tags:
                            lyrics_text = str(audio_file.tags['USLT'])
                        # Alternative text frame
                        elif 'LYRICS' in audio_file.tags:
                            lyrics_text = str(audio_file.tags['LYRICS'])

                    # Vorbis comments (FLAC, OGG)
                    elif hasattr(audio_file, 'get'):
                        lyrics_text = audio_file.get('LYRICS', [None])[0] or audio_file.get('UNSYNCEDLYRICS', [None])[0]

                    # MP4/M4A tags
                    elif hasattr(audio_file, '__getitem__'):
                        try:
                            lyrics_text = audio_file.get('\xa9lyr', [None])[0]
                        except:
                            pass

                if lyrics_text:
                    # Save to database for future requests
                    track.lyrics = lyrics_text
                    library_manager.tracks.update(track)

                    return {
                        "track_id": track_id,
                        "lyrics": lyrics_text,
                        "format": "lrc" if "[" in lyrics_text and "]" in lyrics_text else "plain"
                    }

            except Exception as e:
                logger.error(f"Failed to extract lyrics from file: {e}")

            # No lyrics found
            return {
                "track_id": track_id,
                "lyrics": None,
                "format": None
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get lyrics: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get lyrics: {e}")

    @router.get("/api/library/artists")
    async def get_artists(
        limit: int = 50,
        offset: int = 0,
        order_by: str = "name"
    ):
        """
        Get paginated list of artists.

        Query Parameters:
            limit: Number of artists to return (default 50, max 200)
            offset: Number of artists to skip (default 0)
            order_by: Field to order by - "name", "album_count", or "track_count" (default "name")

        Returns:
            dict: Paginated artists with metadata
            {
                "artists": [...],
                "total": 2000,
                "limit": 50,
                "offset": 0,
                "has_more": true
            }

        Raises:
            HTTPException: If library manager not available or query fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        # Validate and limit pagination parameters
        limit = min(max(limit, 1), 200)  # Between 1-200
        offset = max(offset, 0)  # Non-negative

        # Validate order_by
        valid_order_by = ["name", "album_count", "track_count"]
        if order_by not in valid_order_by:
            order_by = "name"

        try:
            artists, total = library_manager.artists.get_all(
                limit=limit,
                offset=offset,
                order_by=order_by
            )

            # Calculate if there are more results
            has_more = (offset + limit) < total

            return {
                "artists": [artist.to_dict() for artist in artists],
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": has_more
            }
        except Exception as e:
            logger.error(f"Failed to get artists: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get artists: {e}")

    @router.get("/api/library/artists/{artist_id}")
    async def get_artist(artist_id: int):
        """
        Get artist details by ID with albums and tracks.

        Args:
            artist_id: Artist ID

        Returns:
            dict: Artist data with albums and tracks

        Raises:
            HTTPException: If library manager not available or artist not found
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            artist = library_manager.artists.get_by_id(artist_id)
            if not artist:
                raise HTTPException(status_code=404, detail=f"Artist {artist_id} not found")

            return artist.to_dict()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get artist {artist_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get artist: {e}")

    @router.get("/api/library/albums")
    async def get_albums():
        """
        Get all albums.

        Returns:
            dict: List of albums

        Raises:
            HTTPException: If library manager not available or query fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            albums = library_manager.albums.get_all()
            return {
                "albums": [album.to_dict() for album in albums],
                "total": len(albums)
            }
        except Exception as e:
            logger.error(f"Failed to get albums: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get albums: {e}")

    @router.get("/api/library/albums/{album_id}")
    async def get_album(album_id: int):
        """
        Get album details by ID with tracks.

        Args:
            album_id: Album ID

        Returns:
            dict: Album data with tracks

        Raises:
            HTTPException: If library manager not available or album not found
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            album = library_manager.albums.get_by_id(album_id)
            if not album:
                raise HTTPException(status_code=404, detail=f"Album {album_id} not found")

            return album.to_dict()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get album {album_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get album: {e}")

    @router.post("/api/library/scan")
    async def scan_library(
        directories: List[str],
        recursive: bool = True,
        skip_existing: bool = True
    ):
        """
        Scan directories for audio files and add them to the library.

        This endpoint scans the specified directories for audio files and imports them
        into the library. Progress updates are sent via WebSocket (see WEBSOCKET_API.md).

        Args:
            directories: List of directory paths to scan
            recursive: Whether to scan subdirectories (default: True)
            skip_existing: Skip files already in library (default: True)

        Returns:
            dict: Scan result with statistics:
                - files_found: Number of audio files discovered
                - files_added: Number of new files added to library
                - files_skipped: Number of existing files skipped
                - files_failed: Number of files that failed to import
                - scan_time: Total scan duration in seconds
                -
        Raises:
            HTTPException: If library manager not available or scan fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            from auralis.library.scanner import LibraryScanner

            # Create scanner with progress callback
            scanner = LibraryScanner(library_manager)

            # TODO: Connect progress callback to WebSocket broadcast
            # For now, just scan without live progress

            result = scanner.scan_directories(
                directories=directories,
                recursive=recursive,
                skip_existing=skip_existing,
                check_modifications=True
            )

            return {
                "files_found": result.files_found,
                "files_added": result.files_added,
                "files_updated": result.files_updated,
                "files_skipped": result.files_skipped,
                "files_failed": result.files_failed,
                "scan_time": result.scan_time,
                "directories_scanned": result.directories_scanned
            }

        except Exception as e:
            logger.error(f"Library scan failed: {e}")
            raise HTTPException(status_code=500, detail=f"Scan failed: {e}")

    return router
