"""
Files Router
~~~~~~~~~~~~

Handles file operations: directory scanning, file uploads, and supported format queries.

Endpoints:
- POST /api/library/scan - Scan directory for audio files
- POST /api/files/upload - Upload audio files
- GET /api/audio/formats - Get supported audio formats

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from .dependencies import require_library_manager, require_repository_factory

# Import only if available
try:
    from auralis.io.unified_loader import load_audio
    from auralis.library.scanner import LibraryScanner
    HAS_LIBRARY = True
except ImportError:
    HAS_LIBRARY = False

logger = logging.getLogger(__name__)
router = APIRouter(tags=["files"])


class ScanRequest(BaseModel):
    """Request model for directory scanning"""
    directory: str


def create_files_router(
    get_library_manager: Callable[[], Any],
    connection_manager: Any,
    get_repository_factory: Callable[[], Any] | None = None
) -> APIRouter:
    """
    Factory function to create files router with dependencies.

    Args:
        get_library_manager: Callable that returns current LibraryManager instance
        connection_manager: WebSocket connection manager for broadcasts
        get_repository_factory: Callable that returns RepositoryFactory instance (Phase 2 support)

    Returns:
        APIRouter: Configured router instance

    Note:
        Uses LibraryManager for scanning operations as LibraryScanner is tightly coupled to it.
        File upload uses library_manager.add_track() for backward compatibility.
    """

    def get_repos() -> Any:
        """Get repository factory or LibraryManager for accessing repositories."""
        if get_repository_factory:
            try:
                return require_repository_factory(get_repository_factory)
            except (TypeError, AttributeError):
                pass
        return require_library_manager(get_library_manager)

    @router.post("/api/library/scan")
    async def scan_directory(request: ScanRequest) -> dict[str, Any]:
        """
        Scan directory for audio files.

        Starts a background scan task and broadcasts progress/completion via WebSocket.

        Args:
            request: ScanRequest with directory path

        Returns:
            dict: Scan status message

        Raises:
            HTTPException: If library manager not available or scan fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        if not HAS_LIBRARY:
            raise HTTPException(status_code=503, detail="Library scanner not available")

        directory = request.directory

        try:
            scanner = LibraryScanner(library_manager)

            # Start scan in background
            async def scan_worker() -> None:
                try:
                    result = scanner.scan_single_directory(directory, recursive=True)

                    # Broadcast scan completion to all connected clients
                    await connection_manager.broadcast({
                        "type": "scan_complete",
                        "data": {
                            "directory": directory,
                            "files_found": result.files_found,
                            "files_added": result.files_added,
                            "files_updated": result.files_updated,
                            "files_failed": result.files_failed,
                            "scan_time": result.scan_time
                        }
                    })

                except Exception as e:
                    logger.error(f"Scan worker error: {e}")
                    await connection_manager.broadcast({
                        "type": "scan_error",
                        "data": {"directory": directory, "error": str(e)}
                    })

            # Start the scan
            asyncio.create_task(scan_worker())

            return {"message": f"Scan of {directory} started", "status": "scanning"}

        except Exception as e:
            logger.error(f"Failed to start scan: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to start scan: {e}")

    @router.post("/api/files/upload")
    async def upload_files(files: list[UploadFile] = File(...)) -> dict[str, Any]:
        """
        Upload audio files for processing.

        Saves uploaded files to library and extracts metadata.

        Args:
            files: List of uploaded files

        Returns:
            dict: Upload results for each file with metadata

        Raises:
            HTTPException: If no files provided or library unavailable
        """
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        if not HAS_LIBRARY:
            raise HTTPException(status_code=503, detail="Audio processing library not available")

        results: list[dict[str, Any]] = []
        supported_extensions = ('.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac')

        for file in files:
            try:
                # Validate file type
                if not file.filename or not file.filename.lower().endswith(supported_extensions):
                    results.append({
                        "filename": file.filename or "",
                        "status": "error",
                        "message": "Unsupported file type"
                    })
                    continue

                # Save uploaded file to temporary location
                suffix = Path(file.filename).suffix if file.filename else ""
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    content = await file.read()
                    tmp.write(content)
                    temp_path = tmp.name

                try:
                    # Load audio to get metadata (sample rate, duration)
                    audio_data, sample_rate = load_audio(temp_path)
                    duration = len(audio_data) / sample_rate

                    # Extract file name without extension
                    file_stem = Path(file.filename).stem if file.filename else "track"

                    # Create track info dictionary for library
                    track_info = {
                        "filepath": temp_path,
                        "filename": file.filename,
                        "title": file_stem,
                        "duration": duration,
                        "sample_rate": sample_rate,
                        "channels": 1 if audio_data.ndim == 1 else audio_data.shape[1]
                    }

                    # Add track to library
                    track = library_manager.add_track(track_info)

                    if track:
                        results.append({
                            "filename": file.filename or "",
                            "status": "success",
                            "message": "File uploaded and added to library",
                            "track_id": track.id,
                            "title": track.title,
                            "duration": float(track.duration),
                            "sample_rate": track.sample_rate
                        })
                        logger.info(f"Successfully uploaded and processed: {file.filename}")
                    else:
                        results.append({
                            "filename": file.filename or "",
                            "status": "error",
                            "message": "Failed to add track to library"
                        })

                except Exception as e:
                    logger.error(f"Audio processing error for {file.filename}: {e}")
                    results.append({
                        "filename": file.filename or "",
                        "status": "error",
                        "message": f"Failed to process audio: {str(e)}"
                    })

                finally:
                    # Clean up temporary file
                    try:
                        Path(temp_path).unlink()
                    except Exception as e:
                        logger.debug(f"Failed to clean temp file: {e}")

            except Exception as e:
                logger.error(f"Upload error for {file.filename}: {e}")
                results.append({
                    "filename": file.filename or "",
                    "status": "error",
                    "message": str(e)
                })

        return {"results": results}

    @router.get("/api/audio/formats")
    async def get_supported_formats() -> dict[str, Any]:
        """
        Get supported audio formats.

        Returns information about supported input/output formats,
        sample rates, and bit depths.

        Returns:
            dict: Supported formats, sample rates, and bit depths
        """
        return {
            "input_formats": [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"],
            "output_formats": [".wav", ".flac", ".mp3"],
            "sample_rates": [44100, 48000, 88200, 96000, 192000],
            "bit_depths": [16, 24, 32]
        }

    return router
