"""
Processing Upload Endpoint

POST /api/processing/upload-and-process and its upload helpers (size cap,
magic-byte sniff, exclusive-create write). Split out of
routers/processing_api.py (#5472), whose create_processing_router()
registers it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import json
import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from core.processing_engine import ProcessingEngine, ProcessingStatus

from .dependencies import with_error_handling
from .processing_deps import _get_processing_engine
from .processing_models import ProcessingSettings, ProcessResponse

logger = logging.getLogger(__name__)

# Upload security constants (#2560). Single source of truth in config.limits (#4033).
# Derived from the single source of truth (auralis.io.formats) so the upload
# allowlist tracks exactly what the loader can decode (#4109).
from auralis.io.formats import AUDIO_EXTENSIONS as _ALLOWED_AUDIO_EXTENSIONS

from config.limits import MAX_UPLOAD_BYTES as _MAX_UPLOAD_BYTES
from config.limits import UPLOAD_TEMP_DIRNAME, create_secure_temp_dir


def _write_upload(temp_dir: Path, input_path: Path, content: bytes) -> None:
    """Create the upload dir and write *content* with exclusive create.

    Runs in a worker thread via asyncio.to_thread (#4653). "xb" makes the open
    fail with FileExistsError instead of following a symlink planted at the
    path between name selection and open (#2170).
    """
    create_secure_temp_dir(temp_dir)
    with open(input_path, "xb") as f:
        f.write(content)


def _is_valid_audio_magic(data: bytes) -> bool:
    """Return True if data starts with a known audio format magic signature."""
    if len(data) < 8:
        return False
    if data[:4] == b"RIFF":                          # WAV
        return True
    if data[:4] == b"fLaC":                          # FLAC
        return True
    if data[:4] == b"OggS":                          # OGG/Opus
        return True
    if data[:3] == b"ID3":                           # MP3 with ID3v2 tag
        return True
    if data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa"):  # MP3 sync word
        return True
    if data[4:8] == b"ftyp":                         # M4A/MP4 (MPEG-4 container)
        return True
    return data[:4] in (b"FORM", b"AIFF")            # AIFF


@with_error_handling("upload and process")
async def upload_and_process(
    file: UploadFile = File(...),
    settings: str = Form(...),  # JSON string of ProcessingSettings
    engine: ProcessingEngine | None = Depends(_get_processing_engine),
) -> ProcessResponse:
    """
    Upload an audio file and immediately submit for processing.
    Combines file upload and processing submission in one request.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    # Parse settings from JSON string. Malformed client input (bad
    # JSON, or a shape ProcessingSettings rejects) is a 400, not the
    # generic 500 both used to fall through to via a bare
    # `except Exception` — that loose behavior was masked by
    # a test assertion permitting 500 as an acceptable outcome
    # (#4788) until it was tightened and caught this.
    try:
        settings_dict = json.loads(settings)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid settings JSON: {e}")
    try:
        processing_settings = ProcessingSettings(**settings_dict)
    except (TypeError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid processing settings: {e}")
    # This endpoint takes no reference file, so a reference or hybrid job
    # could only ever run as adaptive under the wrong label (#5058). Same
    # 422 as process_audio's missing-reference rejection.
    if processing_settings.requires_reference:
        raise HTTPException(
            status_code=422,
            detail=f"mode={processing_settings.mode!r} requires a reference_path, "
            "which upload does not accept",
        )

    # Save uploaded file to temp location
    temp_dir = Path(tempfile.gettempdir()) / UPLOAD_TEMP_DIRNAME

    # Enforce size limit before reading the whole body (#2560)
    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {_MAX_UPLOAD_BYTES // 1024 // 1024} MB)"
        )

    # Reject files whose magic bytes don't match a known audio format (#2560)
    if not _is_valid_audio_magic(content):
        raise HTTPException(
            status_code=415,
            detail="Unsupported or invalid audio file format"
        )

    # Use a UUID filename to prevent client-controlled path injection (#2560).
    # Open with "xb" (exclusive create) to prevent TOCTOU: if another process
    # created a symlink at this path between path selection and open, the
    # kernel raises FileExistsError rather than following the symlink (fixes #2170).
    original_ext = Path(file.filename or "").suffix.lower()
    if original_ext not in _ALLOWED_AUDIO_EXTENSIONS:
        original_ext = ".bin"
    input_path = temp_dir / f"{uuid.uuid4()}{original_ext}"
    # #4653: the mkdir and the up-to-500 MB write used to run directly on the
    # event loop, stalling WebSocket audio delivery and every other request
    # for the length of the write. Same shape as files.py's _write_temp
    # (#3494). The "xb" exclusive-create mode is kept — it is the #2170
    # anti-TOCTOU guard, not incidental.
    await asyncio.to_thread(_write_upload, temp_dir, input_path, content)

    # Debug, not info (#3844): avoid logging absolute filesystem paths.
    logger.debug(f"Uploaded file saved to {input_path}")

    # Create and submit job — clean up temp file on failure (#3223)
    try:
        job = await engine.create_job(
            input_path=str(input_path),
            settings=processing_settings.model_dump(),
            mode=processing_settings.mode
        )

        try:
            job_id = await engine.submit_job(job)
        except asyncio.QueueFull:
            raise HTTPException(
                status_code=503,
                detail="Processing queue is full, please try again later",
            )

        return ProcessResponse(
            job_id=job_id,
            status=ProcessingStatus.QUEUED,
            message=f"File {file.filename} uploaded and queued for processing"
        )
    except Exception:
        # Clean up orphaned temp file on any failure after write
        input_path.unlink(missing_ok=True)
        raise
