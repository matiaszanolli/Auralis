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

import logging
import mimetypes
from pathlib import Path
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .dependencies import require_repository_factory

logger = logging.getLogger(__name__)
router = APIRouter(tags=["artwork"])


def create_artwork_router(
    connection_manager: Any,
    get_repository_factory: Callable[[], Any]
) -> APIRouter:
    """
    Factory function to create artwork router with dependencies.

    Args:
        connection_manager: WebSocket connection manager for broadcasts
        get_repository_factory: Callable that returns RepositoryFactory instance

    Returns:
        APIRouter: Configured router instance

    Note:
        Phase 6B: Fully migrated to RepositoryFactory pattern (no LibraryManager fallback)
    """

    def get_repos() -> Any:
        """Get repository factory for accessing repositories."""
        return require_repository_factory(get_repository_factory)

    @router.get("/api/albums/{album_id}/artwork")
    async def get_album_artwork(album_id: int) -> FileResponse:
        """
        Get album artwork file (with path traversal protection).

        Args:
            album_id: Album ID

        Returns:
            FileResponse: Artwork image file

        Raises:
            HTTPException: If library manager/factory not available, album/artwork not found,
                         or path validation fails
        """
        try:
            repos = get_repos()
            # Get album to find artwork path
            album = repos.albums.get_by_id(album_id)

            if not album:
                raise HTTPException(status_code=404, detail="Album not found")

            if not album.artwork_path:
                raise HTTPException(status_code=404, detail="Artwork not found")

            # Security: Validate artwork path is within allowed directory
            # Define allowed artwork directory
            artwork_dir = Path.home() / ".auralis" / "artwork"
            artwork_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists

            # Resolve allowed directory (handles symlinks in base path)
            allowed_dir = artwork_dir.resolve()

            # Resolve artwork path (handles symlinks and relative paths)
            # Use strict=False to resolve path even if file doesn't exist (for security validation)
            try:
                requested_path = Path(album.artwork_path).resolve(strict=False)
            except (OSError, RuntimeError, ValueError) as e:
                logger.warning(f"Invalid artwork path for album {album_id}: {album.artwork_path} - {e}")
                raise HTTPException(status_code=403, detail="Access denied: invalid path")

            # Security: Check that resolved path is within allowed directory
            # This MUST happen before existence check to prevent path traversal
            # Use is_relative_to() for safe path comparison (prevents traversal attacks)
            if not requested_path.is_relative_to(allowed_dir):
                logger.warning(
                    f"Path traversal attempt blocked for album {album_id}: "
                    f"requested={requested_path}, allowed_dir={allowed_dir}"
                )
                raise HTTPException(status_code=403, detail="Access denied: path outside artwork directory")

            # Additional check: file must exist (after security validation)
            if not requested_path.exists():
                raise HTTPException(status_code=404, detail="Artwork not found")

            # Detect MIME type from file extension first, then fall back to magic bytes
            # so that PNG files with unrecognized/missing extensions are not served
            # as image/jpeg (fixes #2510).
            media_type, _ = mimetypes.guess_type(str(requested_path))
            if not media_type or not media_type.startswith("image/"):
                # Read the first 12 bytes to identify the format via magic bytes
                try:
                    with open(requested_path, "rb") as _f:
                        header = _f.read(12)
                except OSError:
                    header = b""
                if header[:8] == b"\x89PNG\r\n\x1a\n":
                    media_type = "image/png"
                elif header[:3] == b"\xff\xd8\xff":
                    media_type = "image/jpeg"
                elif header[:4] == b"RIFF" and header[8:12] == b"WEBP":
                    media_type = "image/webp"
                elif header[:4] in (b"GIF8", b"GIF9"):
                    media_type = "image/gif"
                else:
                    media_type = "image/jpeg"  # safest fallback for browsers

            # Return artwork file with validated path
            return FileResponse(
                str(requested_path),  # Use validated absolute path
                media_type=media_type,
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
    async def extract_album_artwork(album_id: int) -> dict[str, Any]:
        """
        Extract artwork from album tracks.

        Extracts embedded artwork from the album's audio files and saves it.

        Args:
            album_id: Album ID

        Returns:
            dict: Success message and artwork URL

        Raises:
            HTTPException: If library manager/factory not available or extraction fails
        """
        try:
            repos = get_repos()
            artwork_path = repos.albums.extract_and_save_artwork(album_id)

            if not artwork_path:
                raise HTTPException(
                    status_code=404,
                    detail="No artwork found in album tracks"
                )

            # Convert filesystem path to API URL
            artwork_url = f"/api/albums/{album_id}/artwork"

            # Broadcast artwork updated event
            await connection_manager.broadcast({
                "type": "artwork_updated",
                "data": {
                    "action": "extracted",
                    "album_id": album_id,
                    "artwork_path": artwork_url
                }
            })

            return {
                "message": "Artwork extracted successfully",
                "artwork_url": artwork_url,  # API URL — consistent with artist serializer (fixes #2508)
                "album_id": album_id
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to extract artwork: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to extract artwork: {e}")

    @router.delete("/api/albums/{album_id}/artwork")
    async def delete_album_artwork(album_id: int) -> dict[str, Any]:
        """
        Delete album artwork.

        Args:
            album_id: Album ID

        Returns:
            dict: Success message

        Raises:
            HTTPException: If library manager/factory not available or artwork not found
        """
        try:
            repos = get_repos()
            success = repos.albums.delete_artwork(album_id)

            if not success:
                raise HTTPException(status_code=404, detail="Artwork not found")

            # Broadcast artwork updated event
            await connection_manager.broadcast({
                "type": "artwork_updated",
                "data": {"action": "deleted", "album_id": album_id}
            })

            return {"message": "Artwork deleted successfully", "album_id": album_id}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete artwork: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete artwork: {e}")

    @router.post("/api/albums/{album_id}/artwork/download")
    async def download_album_artwork(album_id: int) -> dict[str, Any]:
        """
        Download album artwork from online sources.

        Automatically searches and downloads artwork from MusicBrainz and iTunes.

        Args:
            album_id: Album ID

        Returns:
            dict: Success message and artwork path

        Raises:
            HTTPException: If library manager/factory not available or download fails
        """
        try:
            repos = get_repos()
            # Get album using repository (includes eager loading of artist)
            album = repos.albums.get_by_id(album_id)

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

            # Save artwork path to database
            updated_album = repos.albums.update_artwork_path(album_id, artwork_path)
            if not updated_album:
                raise HTTPException(status_code=404, detail="Album not found")

            # Convert filesystem path to API URL
            artwork_url = f"/api/albums/{album_id}/artwork"

            # Broadcast artwork updated event
            await connection_manager.broadcast({
                "type": "artwork_updated",
                "data": {
                    "action": "downloaded",
                    "album_id": album_id,
                    "artwork_path": artwork_url
                }
            })

            return {
                "message": "Artwork downloaded successfully",
                "artwork_path": artwork_url,  # Return URL, not filesystem path
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
