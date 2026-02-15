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

import logging
from typing import Any, cast
from collections.abc import Callable

from fastapi import APIRouter, HTTPException

from schemas import ScanRequest

from .dependencies import require_repository_factory
from .errors import NotFoundError, handle_query_error
from .serializers import (
    serialize_album,
    serialize_albums,
    serialize_artist,
    serialize_artists,
    serialize_tracks,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["library"])


def create_library_router(
    get_repository_factory: Callable[[], Any],
    get_library_manager: Callable[[], Any] | None = None,
    connection_manager: Any | None = None
) -> APIRouter:
    """
    Factory function to create library router with dependencies.

    Args:
        get_repository_factory: Callable that returns RepositoryFactory instance
        get_library_manager: Optional callable that returns LibraryManager instance (for scanning)
        connection_manager: WebSocket connection manager for progress broadcasts (optional)

    Returns:
        APIRouter: Configured router instance

    Note:
        Phase 6B: Fully migrated to RepositoryFactory pattern (no LibraryManager fallback)
    """

    @router.get("/api/library/stats")
    async def get_library_stats() -> dict[str, Any]:
        """
        Get library statistics.

        Returns:
            dict: Library statistics (track count, album count, etc.)

        Raises:
            HTTPException: If repository factory not available or query fails
        """
        try:
            factory = require_repository_factory(get_repository_factory)
            stats = factory.stats.get_library_stats()
            return cast(dict[str, Any], stats)
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get library stats", e)

    @router.get("/api/library/tracks")
    async def get_tracks(
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        order_by: str = 'created_at'
    ) -> dict[str, Any]:
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
            HTTPException: If library manager/factory not available or query fails
        """
        try:
            repos = require_repository_factory(get_repository_factory)

            # Get tracks with pagination
            if search:
                tracks, total = repos.tracks.search(search, limit=limit, offset=offset)
                has_more = (offset + len(tracks)) < total
            else:
                tracks, total = repos.tracks.get_all(limit=limit, offset=offset, order_by=order_by)
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
    async def get_favorite_tracks(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """
        Get all favorite tracks with pagination.

        Args:
            limit: Maximum number of tracks to return (default: 50)
            offset: Number of tracks to skip (default: 0)

        Returns:
            dict: List of favorite tracks with pagination info

        Raises:
            HTTPException: If library manager/factory not available or query fails
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            tracks, total = repos.tracks.get_favorites(limit=limit, offset=offset)
            has_more = (offset + len(tracks)) < total

            return {
                "tracks": serialize_tracks(tracks),
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": has_more
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get favorite tracks", e)

    @router.post("/api/library/tracks/{track_id}/favorite")
    async def set_track_favorite(track_id: int) -> dict[str, Any]:
        """
        Mark track as favorite.

        Args:
            track_id: Track ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager/factory not available or operation fails
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            repos.tracks.set_favorite(track_id, True)
            logger.info(f"Track {track_id} marked as favorite")
            return {"message": "Track marked as favorite", "track_id": track_id, "favorite": True}
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("set track favorite", e)

    @router.delete("/api/library/tracks/{track_id}/favorite")
    async def remove_track_favorite(track_id: int) -> dict[str, Any]:
        """
        Remove track from favorites.

        Args:
            track_id: Track ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager/factory not available or operation fails
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            repos.tracks.set_favorite(track_id, False)
            logger.info(f"Track {track_id} removed from favorites")
            return {"message": "Track removed from favorites", "track_id": track_id, "favorite": False}
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("remove track favorite", e)

    @router.get("/api/library/tracks/{track_id}/lyrics")
    async def get_track_lyrics(track_id: int) -> dict[str, Any]:
        """
        Get lyrics for a track.

        Attempts to retrieve lyrics from database first, then extracts from file if needed.

        Args:
            track_id: Track ID

        Returns:
            dict: Lyrics text and format (lrc or plain), or None if not found

        Raises:
            HTTPException: If library manager/factory not available, track not found, or query fails
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            track = repos.tracks.get_by_id(track_id)
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
                    repos.tracks.update(track_id, lyrics=lyrics_text)

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
    ) -> dict[str, Any]:
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
            HTTPException: If library manager/factory not available or query fails
        """
        try:
            repos = require_repository_factory(get_repository_factory)

            # Validate and limit pagination parameters
            limit = min(max(limit, 1), 200)  # Between 1-200
            offset = max(offset, 0)  # Non-negative

            # Validate order_by
            valid_order_by = ["name", "album_count", "track_count"]
            if order_by not in valid_order_by:
                order_by = "name"

            artists, total = repos.artists.get_all(
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
    async def get_artist(artist_id: int) -> dict[str, Any]:
        """
        Get artist details by ID with albums and tracks.

        Args:
            artist_id: Artist ID

        Returns:
            dict: Artist data with albums and tracks

        Raises:
            HTTPException: If library manager/factory not available or artist not found
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            artist = repos.artists.get_by_id(artist_id)
            if not artist:
                raise NotFoundError("Artist", artist_id)

            return serialize_artist(artist)
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get artist", e)

    @router.get("/api/library/albums")
    async def get_albums() -> dict[str, Any]:
        """
        Get all albums.

        Returns:
            dict: List of albums

        Raises:
            HTTPException: If library manager/factory not available or query fails
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            albums, total = repos.albums.get_all()
            return {
                "albums": serialize_albums(albums),
                "total": total
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get albums", e)

    @router.get("/api/library/albums/{album_id}")
    async def get_album(album_id: int) -> dict[str, Any]:
        """
        Get album details by ID with tracks.

        Args:
            album_id: Album ID

        Returns:
            dict: Album data with tracks

        Raises:
            HTTPException: If library manager/factory not available or album not found
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            album = repos.albums.get_by_id(album_id)
            if not album:
                raise NotFoundError("Album", album_id)

            return serialize_album(album)
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get album", e)

    @router.post("/api/library/scan")
    async def scan_library(request: ScanRequest) -> dict[str, Any]:
        """
        Scan directories for audio files and add them to the library.

        This endpoint scans the specified directories for audio files and imports them
        into the library. Progress updates are sent via WebSocket (see WEBSOCKET_API.md).

        Args:
            request: Scan request containing:
                - directories: List of directory paths to scan
                - recursive: Whether to scan subdirectories (default: True)
                - skip_existing: Skip files already in library (default: True)

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
            from auralis.library.scanner import LibraryScanner

            if not get_library_manager:
                raise HTTPException(status_code=503, detail="Library manager not available")

            library_manager = get_library_manager()

            # Create scanner with progress callback
            scanner = LibraryScanner(library_manager)

            # Define progress callback that broadcasts updates via WebSocket
            async def progress_callback(event_data: dict[str, Any]) -> None:
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
                    directories=request.directories,
                    recursive=request.recursive,
                    skip_existing=request.skip_existing,
                    check_modifications=True,
                    progress_callback=progress_callback  # type: ignore[call-arg]
                )
            except TypeError:
                # Fallback if scanner doesn't support progress_callback parameter
                logger.warning("LibraryScanner does not support progress_callback, scanning without live progress")
                result = scanner.scan_directories(
                    directories=request.directories,
                    recursive=request.recursive,
                    skip_existing=request.skip_existing,
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

    @router.get("/api/library/fingerprints/status")
    async def get_fingerprinting_status() -> dict[str, Any]:
        """
        Get fingerprinting progress for library.

        Returns:
            dict: Fingerprinting status with:
                - total_tracks: Total number of tracks in library
                - fingerprinted_tracks: Number of tracks with fingerprints
                - pending_tracks: Number of tracks waiting for fingerprinting
                - progress_percent: Percentage of fingerprinting complete
                - status: Current status message
        """
        try:
            repos = require_repository_factory(get_repository_factory)

            # Get fingerprint statistics from repository
            stats = repos.fingerprints.get_fingerprint_stats()

            total_tracks = stats['total']
            fingerprinted_count = stats['fingerprinted']
            pending_count = stats['pending']
            progress_percent = stats['progress_percent']

            # Determine status message
            if total_tracks == 0:
                status = "No tracks in library"
            elif fingerprinted_count == total_tracks:
                status = "✅ All tracks fingerprinted"
            elif fingerprinted_count == 0:
                status = "⏳ Waiting to start fingerprinting..."
            else:
                status = f"🔄 Fingerprinting in progress ({fingerprinted_count}/{total_tracks})"

            return {
                "total_tracks": total_tracks,
                "fingerprinted_tracks": fingerprinted_count,
                "pending_tracks": pending_count,
                "progress_percent": progress_percent,
                "status": status,
                "estimated_remaining_seconds": int(pending_count * 30) if pending_count > 0 else 0  # Rough estimate: 30s per track
            }
        except HTTPException:
            raise
        except Exception as e:
            raise handle_query_error("get fingerprinting status", e)

    @router.get("/api/tracks/{track_id}/fingerprint")
    async def get_track_fingerprint(track_id: int) -> dict[str, Any]:
        """
        Get fingerprint for a specific track.

        Returns the 25D audio fingerprint for the track if available.
        Used by the Album Character Pane to show playing track's sonic character.

        Args:
            track_id: Track ID

        Returns:
            dict: Track fingerprint with all 25 dimensions

        Raises:
            HTTPException: If track not found or fingerprint not available
        """
        try:
            logger.info(f"🔍 GET /api/tracks/{track_id}/fingerprint - looking up fingerprint")
            repos = require_repository_factory(get_repository_factory)

            # Verify track exists
            track = repos.tracks.get_by_id(track_id)
            if not track:
                logger.warning(f"❌ Track {track_id} not found in database")
                raise HTTPException(
                    status_code=404,
                    detail=f"Track {track_id} not found"
                )

            logger.info(f"✓ Track found: {track.title} by {track.artists}")

            # Get fingerprint
            fp = repos.fingerprints.get_by_track_id(track_id)
            logger.info(f"🔍 Fingerprint lookup result: {'FOUND' if fp else 'NOT FOUND'}")
            if not fp:
                # Enqueue for background processing if not available
                try:
                    from fingerprint_queue import get_fingerprint_queue
                    queue = get_fingerprint_queue()
                    if queue:
                        queue.enqueue(track_id)
                        logger.info(f"📋 Track {track_id} queued for background fingerprinting")
                except Exception as q_err:
                    logger.debug(f"Could not enqueue track {track_id}: {q_err}")

                raise HTTPException(
                    status_code=404,
                    detail=f"Fingerprint not available for track {track_id}. Queued for generation."
                )

            # Fingerprint found - return it
            logger.info(f"✅ Returning fingerprint for track {track_id}: LUFS={fp.lufs:.1f}, tempo={fp.tempo_bpm:.1f}")
            return {
                "track_id": track_id,
                "track_title": track.title,
                "artist": track.artist,
                "album": track.album,
                "fingerprint": {
                    # 7D Frequency distribution
                    "sub_bass": fp.sub_bass,
                    "bass": fp.bass,
                    "low_mid": fp.low_mid,
                    "mid": fp.mid,
                    "upper_mid": fp.upper_mid,
                    "presence": fp.presence,
                    "air": fp.air,
                    # 3D Loudness/dynamics
                    "lufs": fp.lufs,
                    "crest_db": fp.crest_db,
                    "bass_mid_ratio": fp.bass_mid_ratio,
                    # 4D Temporal
                    "tempo_bpm": fp.tempo_bpm,
                    "rhythm_stability": fp.rhythm_stability,
                    "transient_density": fp.transient_density,
                    "silence_ratio": fp.silence_ratio,
                    # 3D Spectral shape
                    "spectral_centroid": fp.spectral_centroid,
                    "spectral_rolloff": fp.spectral_rolloff,
                    "spectral_flatness": fp.spectral_flatness,
                    # 6D Harmonic content
                    "harmonic_ratio": fp.harmonic_ratio,
                    "percussive_ratio": fp.percussive_ratio,
                    "pitch_confidence": fp.pitch_confidence,
                    "chroma_energy_mean": fp.chroma_energy_mean,
                    "chroma_energy_variance": fp.chroma_energy_variance,
                    "key_strength": fp.key_strength,
                    # 2D Stereo characteristics
                    "stereo_width": fp.stereo_width,
                    "stereo_correlation": fp.stereo_correlation,
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting track fingerprint: {e}", exc_info=True)
            raise handle_query_error("get track fingerprint", e)

    return router
