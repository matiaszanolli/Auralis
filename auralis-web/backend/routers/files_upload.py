"""
POST /api/files/upload handler (split from files.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from auralis.io.formats import SUPPORTED_FORMATS
from auralis.io.audio_probe import get_audio_info
from auralis.library.data_dir import uploads_dir
from auralis.utils.logging import sanitize_log_value
from collections.abc import Callable
from config.limits import MAX_UPLOAD_BYTES as _MAX_UPLOAD_BYTES
from config.limits import MAX_UPLOAD_DIR_BYTES, MAX_UPLOAD_REQUEST_BYTES
from config.limits import MAX_UPLOAD_FILES as _MAX_UPLOAD_FILES
from core.job_error_mapping import _safe_error_message
from fastapi import Depends, File, HTTPException, UploadFile
from pathlib import Path
from typing import Any
from uuid import uuid4
import asyncio
import shutil
import tempfile

from .errors import BadRequestError
from .files_deps import _get_repos_provider
from .files_upload_budget import UploadBudget, UploadQuotaFull
from .files_validation import _has_valid_audio_magic

logger = logging.getLogger(__name__)


def _remove_quietly(path: str | Path, what: str) -> None:
    """Best-effort cleanup: a file that cannot be removed is logged, never raised."""
    try:
        Path(path).unlink(missing_ok=True)
    except Exception as e:
        logger.debug(f"Failed to clean {what}: {e}")


async def upload_files(
    files: list[UploadFile] = File(...),
    get_repos: Callable[[], Any] = Depends(_get_repos_provider),
) -> dict[str, Any]:
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
        raise BadRequestError("No files provided")

    # Cap the file count before decoding anything (#4349): reject an
    # over-large batch with 413 rather than looping over every element.
    if len(files) > _MAX_UPLOAD_FILES:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files in one request (max {_MAX_UPLOAD_FILES})",
        )

    repos = get_repos()
    upload_dir = uploads_dir()  # follows AURALIS_DATA_DIR, and is on the path allowlist (#6513)
    budget = UploadBudget(MAX_UPLOAD_REQUEST_BYTES, MAX_UPLOAD_DIR_BYTES, upload_dir)

    results: list[dict[str, Any]] = []
    supported_extensions = tuple(SUPPORTED_FORMATS.keys())

    for file in files:
        try:
            # Validate file type
            if not file.filename or not file.filename.lower().endswith(supported_extensions):
                # Log rejected uploads for security audit trail (fixes #2421).
                logger.warning(
                    f"Rejected upload of unsupported file type: {file.filename!r}"
                )
                results.append({
                    "filename": file.filename or "",
                    "status": "error",
                    "message": "Unsupported file type"
                })
                continue

            # Save uploaded file to temporary location.
            # Cap the handler's in-memory read (fixes #3494 / BE-NEW-36 —
            # prior code did `await file.read()` with no size limit and only
            # checked the cap AFTER reading, so a 2 GB POST OOM'd the backend
            # before rejection). Starlette has already spooled the whole
            # multipart body into the UploadFile before this runs (#5270), so
            # this bounds what we materialize into memory, not what came off
            # the wire. +1 lets us detect overflow via length compare.
            suffix = Path(file.filename).suffix if file.filename else ""
            content = await file.read(_MAX_UPLOAD_BYTES + 1)
            if len(content) > _MAX_UPLOAD_BYTES:
                logger.warning(f"Rejected oversized upload: {file.filename!r} ({len(content)} bytes)")
                results.append({
                    "filename": file.filename or "",
                    "status": "error",
                    "message": "File exceeds maximum upload size of 500 MB"
                })
                continue

            if not budget.admit_request(len(content)):
                logger.warning(f"Rejected upload over the per-request byte budget: {file.filename!r}")
                results.append({
                    "filename": file.filename or "",
                    "status": "error",
                    "message": f"Request exceeds the {MAX_UPLOAD_REQUEST_BYTES // 2**30} GiB upload budget",
                })
                continue

            # Validate magic bytes before invoking audio parser (issue #2415)
            if not _has_valid_audio_magic(content):
                logger.warning(
                    f"Rejected upload with invalid audio content: {file.filename!r}"
                )
                results.append({
                    "filename": file.filename or "",
                    "status": "error",
                    "message": "File content does not match any known audio format"
                })
                continue

            # Sync ops below — temp write, audio decode, file move, DB
            # insert — are wrapped in asyncio.to_thread so the event
            # loop isn't blocked for the (often multi-hundred-ms)
            # duration of an upload (fixes #3494 / BE-NEW-36).
            def _write_temp(content_bytes: bytes, suffix_str: str) -> str:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix_str) as tmp:
                    tmp.write(content_bytes)
                    return tmp.name

            temp_path = await asyncio.to_thread(_write_temp, content, suffix)
            permanent_path: Path | None = None
            track_added = False

            try:
                # Read the header for duration / sample rate / channels. This used to decode
                # the whole track (up to the multi-GiB decode budget) and keep both the
                # upload bytes and the decoded array alive just to take three numbers (#5962).
                content = b""  # the bytes are on disk now; do not hold up to 500 MB through the move/insert
                info = await asyncio.to_thread(get_audio_info, temp_path)
                sample_rate = info.get("sample_rate")
                channels = info.get("channels")
                duration = info.get("duration_seconds")
                if info.get("error") or not (sample_rate and channels and duration):
                    raise ValueError("The audio header could not be read")

                # Move to permanent library storage before committing the DB record
                # (issue #2392: storing temp_path then deleting it made every upload
                # unplayable immediately after the finally block ran).
                size = (await asyncio.to_thread(Path(temp_path).stat)).st_size
                if not await budget.admit_storage(size):
                    raise UploadQuotaFull()
                await asyncio.to_thread(upload_dir.mkdir, parents=True, exist_ok=True)
                permanent_path = upload_dir / f"{uuid4().hex}{suffix}"
                await asyncio.to_thread(shutil.move, str(temp_path), str(permanent_path))
                budget.record_stored(size)

                # Extract file name without extension
                file_stem = Path(file.filename).stem if file.filename else "track"

                # Create track info dictionary for library
                track_info = {
                    "filepath": str(permanent_path),  # permanent, not temp (issue #2392)
                    "filename": file.filename,
                    "title": file_stem,
                    "duration": duration,
                    "sample_rate": sample_rate,
                    "channels": channels,
                }

                # Add track to library via repository
                track = await asyncio.to_thread(repos.tracks.add, track_info)

                if track:
                    track_added = True
                    results.append({
                        "filename": file.filename or "",
                        "status": "success",
                        "message": "File uploaded and added to library",
                        "track_id": track.id,
                        "title": track.title,
                        "duration": float(track.duration),
                        "sample_rate": track.sample_rate
                    })
                    logger.info(f"Successfully uploaded and processed: {sanitize_log_value(file.filename)}")
                else:
                    results.append({
                        "filename": file.filename or "",
                        "status": "error",
                        "message": "Failed to add track to library"
                    })

            except UploadQuotaFull:
                logger.warning(f"Rejected upload, uploads directory is at its quota: {sanitize_log_value(file.filename)}")
                results.append({
                    "filename": file.filename or "",
                    "status": "error",
                    "message": f"Upload storage is full ({MAX_UPLOAD_DIR_BYTES // 2**30} GiB); remove tracks to free space",
                })

            except Exception as e:
                logger.error(f"Audio processing error for {sanitize_log_value(file.filename)}: {e}", exc_info=True)
                results.append({
                    "filename": file.filename or "",
                    "status": "error",
                    "message": f"Failed to process audio: {_safe_error_message(e)}"
                })

            finally:
                # shutil.move already removed the temp file on success; unlink is a
                # no-op (missing_ok) in that case. On failure the temp file still
                # exists and must be cleaned up here.
                _remove_quietly(temp_path, "temp file")
                # The file was moved into the uploads directory before the DB insert; if the insert
                # failed (or returned None) nothing references it, and it stayed there forever (#5968).
                if permanent_path is not None and not track_added:
                    _remove_quietly(permanent_path, "orphaned upload")

        except Exception as e:
            logger.error(f"Upload error for {sanitize_log_value(file.filename)}: {e}", exc_info=True)
            results.append({
                "filename": file.filename or "",
                "status": "error",
                "message": _safe_error_message(e)
            })

    return {"results": results}
