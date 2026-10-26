"""
Artwork Router
~~~~~~~~~~~~~~

Handles album artwork operations: retrieval, extraction, and deletion.

Endpoints:
- GET /api/albums/{album_id}/artwork - Get album artwork file
- POST /api/albums/{album_id}/artwork/extract - Extract artwork from tracks
- DELETE /api/albums/{album_id}/artwork - Delete album artwork

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import mimetypes
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, Response

from .dependencies import with_error_handling
from . import artwork_thumbnails
from .errors import NotFoundError
from .artwork_models import ArtworkDeleteResponse, ArtworkDownloadResponse, ArtworkExtractResponse
from .artwork_thumbnails import _get_or_create_thumbnail
from .artwork_deps import _ArtworkDeps, _deps, _repo_deps
from .artwork_manage import (
    delete_album_artwork,
    download_album_artwork,
    extract_album_artwork,
)

logger = logging.getLogger(__name__)


# NOTE: GET /api/albums/{album_id}/artwork has no response_model on purpose —
# it returns raw image bytes (FileResponse/Response), not JSON. Same for the
# other binary routes in this codebase; only the JSON routes below are typed.


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_artwork_router() used to be a 330-line closure: every handler below
# was nested inside it purely to reach connection_manager/get_repository_factory
# via closure capture, which made a handler impossible to import or call
# without first building the whole router. Handlers are now module level; they
# reach the same callables through FastAPI Depends() instead.
#
# Factory calls can coexist in one process (the live app plus throwaway test
# apps), so each router publishes its own deps through a request ContextVar.
# The module-level holder is only the fallback for direct handler calls where
# no router-level dependency ran (#5262).
#
# A handler's Depends() default is only consulted when FastAPI itself
# invokes it for a real request; a direct unit-test call passes the
# service/dependency explicitly as a keyword argument and never touches
# _ArtworkDeps at all -- that's the seam #4670 asked for.
# ============================================================================


@with_error_handling("get artwork")
async def get_album_artwork(
    album_id: Annotated[int, PathParam(ge=1)],
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
    repos: Any = Depends(_repo_deps.get_repos),
) -> Response:
    """
    Get album artwork file (with path traversal protection).

    Args:
        album_id: Album ID
        size: Optional max dimension for a downscaled thumbnail variant.

    Returns:
        FileResponse: Artwork image file (or a size-appropriate thumbnail).

    Raises:
        HTTPException: If the library is not available, album/artwork not found,
                     or path validation fails
    """
    # Get album to find artwork path
    album = await asyncio.to_thread(repos.albums.get_by_id, album_id)

    if not album:
        raise NotFoundError("Album")

    if not album.artwork_path:
        raise NotFoundError("Artwork")

    # Security: Validate artwork path is within allowed directory
    # Define allowed artwork directory (shared with the purge path, #4532)
    artwork_dir, thumb_dir = artwork_thumbnails._artwork_dirs()
    # Off the event loop (#4653's CONSISTENCY sweep): this is inside async def.
    await asyncio.to_thread(artwork_dir.mkdir, parents=True, exist_ok=True)

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
    media_type, _ = mimetypes.guess_file_type(requested_path)
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
    """
    deps = _ArtworkDeps(connection_manager)

    router = APIRouter(
        tags=["artwork"],
        dependencies=[
            Depends(_repo_deps.bind(get_repository_factory)),
            Depends(_deps.bind(deps)),
        ],
    )

    # GET stays first: it is the only route on the bare `/artwork` path, and the
    # `/artwork/extract` + `/artwork/download` literals below must keep their
    # original relative order for path matching to be unchanged.
    router.add_api_route("/api/albums/{album_id}/artwork", get_album_artwork, methods=["GET"])
    router.add_api_route(
        "/api/albums/{album_id}/artwork/extract", extract_album_artwork,
        methods=["POST"], response_model=ArtworkExtractResponse,
    )
    router.add_api_route(
        "/api/albums/{album_id}/artwork", delete_album_artwork,
        methods=["DELETE"], response_model=ArtworkDeleteResponse,
    )
    router.add_api_route(
        "/api/albums/{album_id}/artwork/download", download_album_artwork,
        methods=["POST"], response_model=ArtworkDownloadResponse,
    )

    return router
