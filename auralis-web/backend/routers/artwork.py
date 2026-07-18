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

import asyncio
import hashlib
import logging
import mimetypes
from pathlib import Path
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response

from .dependencies import require_repository_factory, with_error_handling
from .errors import NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["artwork"])

# Downscaled-thumbnail support (#4447). Requested sizes snap UP to one of these
# buckets so the on-disk cache holds at most len(_THUMB_BUCKETS) variants per
# source image instead of an unbounded set of arbitrary sizes.
_THUMB_BUCKETS: tuple[int, ...] = (64, 128, 256, 512, 1024)


def _bucket_size(size: int) -> int:
    """Snap a requested max-dimension up to the nearest cache bucket."""
    for bucket in _THUMB_BUCKETS:
        if size <= bucket:
            return bucket
    return _THUMB_BUCKETS[-1]


def _thumb_target(media_type: str) -> tuple[str, str, str]:
    """Map a source media type to (PIL format, file extension, response type).

    JPEG stays JPEG; WEBP stays WEBP; everything else (PNG/GIF/unknown) is
    rendered as PNG so transparency is preserved.
    """
    if media_type == "image/jpeg":
        return "JPEG", ".jpg", "image/jpeg"
    if media_type == "image/webp":
        return "WEBP", ".webp", "image/webp"
    return "PNG", ".png", "image/png"


def _get_or_create_thumbnail(
    src: Path, requested_size: int, media_type: str, thumb_dir: Path
) -> tuple[Path, str] | None:
    """Return (thumbnail_path, media_type) for a downscaled copy of ``src``.

    Blocking (PIL + disk IO) — call via ``asyncio.to_thread``. The cache key
    includes the source path hash, bucketed size, and source mtime/size so an
    artwork edit produces a new file and stale thumbnails are never served.
    Returns ``None`` on any failure so the caller can fall back to the original.
    """
    try:
        from PIL import Image

        bucket = _bucket_size(requested_size)
        pil_fmt, ext, resp_type = _thumb_target(media_type)

        stat = src.stat()
        path_hash = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:12]
        key = f"{path_hash}_{bucket}_{stat.st_mtime_ns:x}_{stat.st_size:x}{ext}"
        dst = thumb_dir / key

        if not dst.exists():
            thumb_dir.mkdir(parents=True, exist_ok=True)
            with Image.open(src) as image:
                # thumbnail() preserves aspect ratio and only ever downsizes, so
                # a small source is served as-is rather than upscaled.
                image.thumbnail((bucket, bucket))
                if pil_fmt == "JPEG" and image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                # Write atomically-ish: render to a temp then rename so a
                # concurrent request never reads a half-written file.
                tmp = dst.with_suffix(dst.suffix + ".tmp")
                image.save(tmp, format=pil_fmt)
                tmp.replace(dst)

        return dst, resp_type
    except Exception:
        logger.exception("Thumbnail generation failed for %s", src)
        return None


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
    @with_error_handling("get artwork")
    async def get_album_artwork(
        album_id: int,
        request: Request,
        size: int | None = Query(
            None,
            ge=16,
            le=2048,
            description=(
                "Optional max dimension (px) for a downscaled thumbnail. Snaps "
                "up to a cache bucket; omit for the full-resolution image (#4447)."
            ),
        ),
    ) -> Response:
        """
        Get album artwork file (with path traversal protection).

        Args:
            album_id: Album ID
            size: Optional max dimension for a downscaled thumbnail variant.

        Returns:
            FileResponse: Artwork image file (or a size-appropriate thumbnail).

        Raises:
            HTTPException: If library manager/factory not available, album/artwork not found,
                         or path validation fails
        """
        repos = get_repos()
        # Get album to find artwork path
        album = await asyncio.to_thread(repos.albums.get_by_id, album_id)

        if not album:
            raise NotFoundError("Album")

        if not album.artwork_path:
            raise NotFoundError("Artwork")

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
            raise NotFoundError("Artwork")

        # Detect MIME type from file extension first, then fall back to magic bytes
        # so that PNG files with unrecognized/missing extensions are not served
        # as image/jpeg (fixes #2510).
        media_type, _ = mimetypes.guess_type(str(requested_path))
        if not media_type or not media_type.startswith("image/"):
            # Read the first 12 bytes to identify the format via magic bytes
            def _read_header() -> bytes:
                try:
                    with open(requested_path, "rb") as _f:
                        return _f.read(12)
                except OSError:
                    return b""
            header = await asyncio.to_thread(_read_header)
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

        # If a thumbnail size was requested, serve a downscaled variant instead
        # of the full-resolution bitmap (#4447). On any failure we fall back to
        # the original, so a broken/unsupported image never 500s the request.
        serve_path = requested_path
        serve_media_type = media_type
        if size is not None:
            thumb_dir = artwork_dir / "thumbnails"
            thumbnail = await asyncio.to_thread(
                _get_or_create_thumbnail, requested_path, size, media_type, thumb_dir
            )
            if thumbnail is not None:
                serve_path, serve_media_type = thumbnail

        # Build ETag from the SERVED file's stat for conditional caching (#2864).
        stat = serve_path.stat()
        etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'

        # If client already has this version, return 304 (no body).
        if_none_match = request.headers.get("if-none-match")
        if if_none_match and if_none_match == etag:
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "Cache-Control": "public, no-cache",
                },
            )

        # Return artwork file with ETag for conditional caching.
        # no-cache = always revalidate, but 304 avoids re-download
        # when content hasn't changed.
        return FileResponse(
            str(serve_path),
            media_type=serve_media_type,
            headers={
                "ETag": etag,
                "Cache-Control": "public, no-cache",
            },
        )

    @router.post("/api/albums/{album_id}/artwork/extract")
    @with_error_handling("extract artwork")
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
        repos = get_repos()
        artwork_path = await asyncio.to_thread(repos.albums.extract_and_save_artwork, album_id)

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
                "artwork_url": artwork_url
            }
        })

        return {
            "message": "Artwork extracted successfully",
            "artwork_url": artwork_url,  # API URL — consistent with artist serializer (fixes #2508)
            "album_id": album_id
        }

    @router.delete("/api/albums/{album_id}/artwork")
    @with_error_handling("delete artwork")
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
        repos = get_repos()
        # Idempotent DELETE per RFC 7231 §4.3.5 — a repeat call after a
        # successful delete should NOT 404 (#3563 / BE-NEW-105). Only
        # 404 when the album itself doesn't exist; if artwork is
        # already gone, return success.
        album = await asyncio.to_thread(repos.albums.get_by_id, album_id)
        if album is None:
            raise NotFoundError("Album", album_id)
        success = await asyncio.to_thread(repos.albums.delete_artwork, album_id)
        # If repo returns False the artwork was already absent — also
        # success from the client's idempotency perspective.

        # Broadcast artwork updated event (only when something actually changed)
        if success:
            await connection_manager.broadcast({
                "type": "artwork_updated",
                "data": {"action": "deleted", "album_id": album_id}
            })

        return {"message": "Artwork deleted successfully", "album_id": album_id}

    @router.post("/api/albums/{album_id}/artwork/download")
    @with_error_handling("download artwork")
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
        repos = get_repos()
        # Get album using repository (includes eager loading of artist)
        album = await asyncio.to_thread(repos.albums.get_by_id, album_id)

        if not album:
            raise NotFoundError("Album")

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
        updated_album = await asyncio.to_thread(repos.albums.update_artwork_path, album_id, artwork_path)
        if not updated_album:
            raise NotFoundError("Album")

        # Convert filesystem path to API URL
        artwork_url = f"/api/albums/{album_id}/artwork"

        # Broadcast artwork updated event
        await connection_manager.broadcast({
            "type": "artwork_updated",
            "data": {
                "action": "downloaded",
                "album_id": album_id,
                "artwork_url": artwork_url
            }
        })

        return {
            "message": "Artwork downloaded successfully",
            "artwork_url": artwork_url,  # API URL, not filesystem path
            "album_id": album_id,
            "artist": artist_name,
            "album": album_name
        }

    return router
