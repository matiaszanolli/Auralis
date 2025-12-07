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
from typing import Optional, List, Dict, Any, Callable
import logging

from .dependencies import require_library_manager
from .errors import (
    LibraryManagerUnavailableError,
    InternalServerError,
    NotFoundError,
    handle_query_error
)
from .serializers import (
    serialize_tracks,
    serialize_albums,
    serialize_artists,
    serialize_album,
    serialize_artist
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["library"])


def create_library_router(get_library_manager: Callable[[], Any], connection_manager: Optional[Any] = None) -> APIRouter:
    """
    Factory function to create library router with dependencies.

    Args:
        get_library_manager: Callable that returns LibraryManager instance
        connection_manager: WebSocket connection manager for progress broadcasts (optional)

    Returns:
        APIRouter: Configured router instance
    """

    @router.get("/api/library/stats")
    async def get_library_stats() -> Dict[str, Any]:
        """
        Get library statistics.

        Returns:
            dict: Library statistics (track count, album count, etc.)

        Raises:
            HTTPException: If library manager not available or query fails
        """
        try:
            library_manager = require_library_manager(get_library_manager)
            stats = library_manager.get_library_stats()
            return stats
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get library stats", e)

    @router.get("/api/library/tracks")
    async def get_tracks(
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        order_by: str = 'created_at'
    ) -> Dict[str, Any]:
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
        try:
            library_manager = require_library_manager(get_library_manager)

            # Get tracks with pagination
            if search:
                tracks = library_manager.search_tracks(search, limit=limit, offset=offset)
                # For search, we don't have total count yet, so estimate
                total = len(tracks) + offset
                has_more = len(tracks) >= limit
            else:
                tracks, total = library_manager.get_all_tracks(limit=limit, offset=offset, order_by=order_by)
                has_more = (offset + len(tracks)) < total

            return {
                "tracks": serialize_tracks(tracks),
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get tracks", e)

    @router.get("/api/library/tracks/favorites")
    async def get_favorite_tracks(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
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
        try:
            library_manager = require_library_manager(get_library_manager)
            tracks = library_manager.get_favorite_tracks(limit=limit, offset=offset)

            # Calculate has_more (we don't have total count for favorites, so estimate)
            has_more = len(tracks) >= limit

            return {
                "tracks": serialize_tracks(tracks),
                "total": len(tracks) + offset,
                "limit": limit,
                "offset": offset,
                "has_more": has_more
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get favorite tracks", e)

    @router.post("/api/library/tracks/{track_id}/favorite")
    async def set_track_favorite(track_id: int) -> Dict[str, Any]:
        """
        Mark track as favorite.

        Args:
            track_id: Track ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager not available or operation fails
        """
        try:
            library_manager = require_library_manager(get_library_manager)
            library_manager.tracks.set_favorite(track_id, True)
            logger.info(f"Track {track_id} marked as favorite")
            return {"message": "Track marked as favorite", "track_id": track_id, "favorite": True}
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("set track favorite", e)

    @router.delete("/api/library/tracks/{track_id}/favorite")
    async def remove_track_favorite(track_id: int) -> Dict[str, Any]:
        """
        Remove track from favorites.

        Args:
            track_id: Track ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager not available or operation fails
        """
        try:
            library_manager = require_library_manager(get_library_manager)
            library_manager.tracks.set_favorite(track_id, False)
            logger.info(f"Track {track_id} removed from favorites")
            return {"message": "Track removed from favorites", "track_id": track_id, "favorite": False}
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("remove track favorite", e)

    @router.get("/api/library/tracks/{track_id}/lyrics")
    async def get_track_lyrics(track_id: int) -> Dict[str, Any]:
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
        try:
            library_manager = require_library_manager(get_library_manager)
            track = library_manager.tracks.get_by_id(track_id)
            if not track:
                raise NotFoundError("Track", track_id)

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
                audio_file = mutagen.File(track.filepath)  # type: ignore[attr-defined]

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
                    track.lyrics = lyrics_text  # type: ignore[assignment]
                    library_manager.tracks.update(track)  # type: ignore[call-arg]

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
            raise handle_query_error("get track lyrics", e)

    @router.get("/api/library/artists")
    async def get_artists(
        limit: int = 50,
        offset: int = 0,
        order_by: str = "name"
    ) -> Dict[str, Any]:
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
        try:
            library_manager = require_library_manager(get_library_manager)

            # Validate and limit pagination parameters
            limit = min(max(limit, 1), 200)  # Between 1-200
            offset = max(offset, 0)  # Non-negative

            # Validate order_by
            valid_order_by = ["name", "album_count", "track_count"]
            if order_by not in valid_order_by:
                order_by = "name"

            artists, total = library_manager.artists.get_all(
                limit=limit,
                offset=offset,
                order_by=order_by
            )

            # Calculate if there are more results
            has_more = (offset + limit) < total

            return {
                "artists": serialize_artists(artists),
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": has_more
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get artists", e)

    @router.get("/api/library/artists/{artist_id}")
    async def get_artist(artist_id: int) -> Dict[str, Any]:
        """
        Get artist details by ID with albums and tracks.

        Args:
            artist_id: Artist ID

        Returns:
            dict: Artist data with albums and tracks

        Raises:
            HTTPException: If library manager not available or artist not found
        """
        try:
            library_manager = require_library_manager(get_library_manager)
            artist = library_manager.artists.get_by_id(artist_id)
            if not artist:
                raise NotFoundError("Artist", artist_id)

            return serialize_artist(artist)
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get artist", e)

    @router.get("/api/library/albums")
    async def get_albums() -> Dict[str, Any]:
        """
        Get all albums.

        Returns:
            dict: List of albums

        Raises:
            HTTPException: If library manager not available or query fails
        """
        try:
            library_manager = require_library_manager(get_library_manager)
            albums, total = library_manager.albums.get_all()
            return {
                "albums": serialize_albums(albums),
                "total": total
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get albums", e)

    @router.get("/api/library/albums/{album_id}")
    async def get_album(album_id: int) -> Dict[str, Any]:
        """
        Get album details by ID with tracks.

        Args:
            album_id: Album ID

        Returns:
            dict: Album data with tracks

        Raises:
            HTTPException: If library manager not available or album not found
        """
        try:
            library_manager = require_library_manager(get_library_manager)
            album = library_manager.albums.get_by_id(album_id)
            if not album:
                raise NotFoundError("Album", album_id)

            return serialize_album(album)
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get album", e)

    @router.post("/api/library/scan")
    async def scan_library(
        directories: List[str],
        recursive: bool = True,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
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

        Raises:
            HTTPException: If library manager not available or scan fails
        """
        try:
            library_manager = require_library_manager(get_library_manager)
            from auralis.library.scanner import LibraryScanner

            # Create scanner with progress callback
            scanner = LibraryScanner(library_manager)

            # Define progress callback that broadcasts updates via WebSocket
            async def progress_callback(event_data: Dict[str, Any]) -> None:
                """
                Broadcast scan progress to connected WebSocket clients.

                Args:
                    event_data: Progress event data with keys:
                        - status: Current status (scanning, importing, etc.)
                        - files_found: Number of files found so far
                        - files_processed: Number of files processed
                        - files_added: Number of files added
                        - current_file: Current file being processed
                        - error: Error message if any
                """
                if connection_manager:
                    await connection_manager.broadcast({
                        "type": "library_scan_progress",
                        "data": event_data
                    })
                    logger.debug(f"Broadcast scan progress: {event_data.get('status')}")

            # Run scan with progress callback
            # Note: The scanner.scan_directories should support an optional progress_callback parameter
            # If not, this will gracefully fall back to scanning without live progress
            try:
                result = scanner.scan_directories(
                    directories=directories,
                    recursive=recursive,
                    skip_existing=skip_existing,
                    check_modifications=True,
                    progress_callback=progress_callback  # type: ignore[call-arg]
                )
            except TypeError:
                # Fallback if scanner doesn't support progress_callback parameter
                logger.warning("LibraryScanner does not support progress_callback, scanning without live progress")
                result = scanner.scan_directories(
                    directories=directories,
                    recursive=recursive,
                    skip_existing=skip_existing,
                    check_modifications=True
                )

            # Broadcast final scan result to all clients
            if connection_manager:
                await connection_manager.broadcast({
                    "type": "library_scan_complete",
                    "data": {
                        "files_found": result.files_found,
                        "files_added": result.files_added,
                        "files_updated": result.files_updated,
                        "files_skipped": result.files_skipped,
                        "files_failed": result.files_failed,
                        "scan_time": result.scan_time,
                        "directories_scanned": result.directories_scanned
                    }
                })

            return {
                "files_found": result.files_found,
                "files_added": result.files_added,
                "files_updated": result.files_updated,
                "files_skipped": result.files_skipped,
                "files_failed": result.files_failed,
                "scan_time": result.scan_time,
                "directories_scanned": result.directories_scanned
            }

        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("scan library", e)

    return router
