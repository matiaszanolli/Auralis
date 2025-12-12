"""
Artwork Router
~~~~~~~~~~~~~~

Handles album artwork operations: retrieval, extraction, and deletion.

Endpoints:
- GET /api/albums/{album_id}/artwork - Get album artwork file
- POST /api/albums/{album_id}/artwork/extract - Extract artwork from tracks
- DELETE /api/albums/{album_id}/artwork - Delete album artwork

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["artwork"])


def create_artwork_router(get_library_manager, connection_manager):
    """
    Factory function to create artwork router with dependencies.

    Args:
        get_library_manager: Callable that returns LibraryManager instance
        connection_manager: WebSocket connection manager for broadcasts

    Returns:
        APIRouter: Configured router instance
    """

    @router.get("/api/albums/{album_id}/artwork")
    async def get_album_artwork(album_id: int):
        """
        Get album artwork file.

        Args:
            album_id: Album ID

        Returns:
            FileResponse: Artwork image file

        Raises:
            HTTPException: If library manager not available, album/artwork not found
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            # Get album to find artwork path using repository
            album = library_manager.albums.get_by_id(album_id)

            if not album:
                raise HTTPException(status_code=404, detail="Album not found")

            if not album.artwork_path or not Path(album.artwork_path).exists():
                raise HTTPException(status_code=404, detail="Artwork not found")

            # Return artwork file
            return FileResponse(
                album.artwork_path,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "public, max-age=31536000",  # Cache for 1 year
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get artwork: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get artwork: {e}")

    @router.post("/api/albums/{album_id}/artwork/extract")
    async def extract_album_artwork(album_id: int):
        """
        Extract artwork from album tracks.

        Extracts embedded artwork from the album's audio files and saves it.

        Args:
            album_id: Album ID

        Returns:
            dict: Success message and artwork path

        Raises:
            HTTPException: If library manager not available or extraction fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            artwork_path = library_manager.albums.extract_and_save_artwork(album_id)

            if not artwork_path:
                raise HTTPException(
                    status_code=404,
                    detail="No artwork found in album tracks"
                )

            # Broadcast artwork extracted event
            await connection_manager.broadcast({
                "type": "artwork_extracted",
                "data": {
                    "album_id": album_id,
                    "artwork_path": artwork_path
                }
            })

            return {
                "message": "Artwork extracted successfully",
                "artwork_path": artwork_path,
                "album_id": album_id
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to extract artwork: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to extract artwork: {e}")

    @router.delete("/api/albums/{album_id}/artwork")
    async def delete_album_artwork(album_id: int):
        """
        Delete album artwork.

        Args:
            album_id: Album ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager not available or artwork not found
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            success = library_manager.albums.delete_artwork(album_id)

            if not success:
                raise HTTPException(status_code=404, detail="Artwork not found")

            # Broadcast artwork deleted event
            await connection_manager.broadcast({
                "type": "artwork_deleted",
                "data": {"album_id": album_id}
            })

            return {"message": "Artwork deleted successfully", "album_id": album_id}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete artwork: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete artwork: {e}")

    @router.post("/api/albums/{album_id}/artwork/download")
    async def download_album_artwork(album_id: int):
        """
        Download album artwork from online sources.

        Automatically searches and downloads artwork from MusicBrainz and iTunes.

        Args:
            album_id: Album ID

        Returns:
            dict: Success message and artwork path

        Raises:
            HTTPException: If library manager not available or download fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            # Get album info
            # Get album using repository (includes eager loading of artist)
            album = library_manager.albums.get_by_id(album_id)

            if not album:
                raise HTTPException(status_code=404, detail="Album not found")

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
                raise HTTPException(
                    status_code=404,
                    detail=f"No artwork found online for '{album_name}' by '{artist_name}'"
                )

            # Save artwork path to database using repository
            updated_album = library_manager.albums.update_artwork_path(album_id, artwork_path)
            if not updated_album:
                raise HTTPException(status_code=404, detail="Album not found")

            # Broadcast artwork downloaded event
            await connection_manager.broadcast({
                "type": "artwork_downloaded",
                "data": {
                    "album_id": album_id,
                    "artwork_path": artwork_path,
                    "artist": artist_name,
                    "album": album_name
                }
            })

            return {
                "message": "Artwork downloaded successfully",
                "artwork_path": artwork_path,
                "album_id": album_id,
                "artist": artist_name,
                "album": album_name
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to download artwork: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to download artwork: {e}")

    return router
