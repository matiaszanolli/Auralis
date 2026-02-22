#!/usr/bin/env python3

"""
Processing API Routes
~~~~~~~~~~~~~~~~~~~~~

FastAPI routes for audio processing functionality.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import struct
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from core.processing_engine import ProcessingEngine, ProcessingStatus
from pydantic import BaseModel
from security.path_security import PathValidationError, validate_file_path

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/processing", tags=["audio-processing"])

# Upload security constants (#2560)
_MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB hard limit
_ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".aiff", ".aif", ".opus"}


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
    if data[:4] in (b"FORM", b"AIFF"):               # AIFF
        return True
    return False

# Global processing engine (will be injected)
_processing_engine: ProcessingEngine | None = None


def set_processing_engine(engine: ProcessingEngine) -> None:
    """Set the global processing engine"""
    global _processing_engine
    _processing_engine = engine


# Pydantic models for request/response
class ProcessingSettings(BaseModel):
    """Processing settings from UI"""
    mode: str = "adaptive"  # "adaptive", "reference", "hybrid"
    output_format: str = "wav"  # "wav", "flac", "mp3"
    bit_depth: int = 16  # 16, 24, 32
    sample_rate: int | None = None  # None = keep original

    # EQ settings
    eq: dict[str, Any] | None = None

    # Dynamics settings
    dynamics: dict[str, Any] | None = None

    # Level matching settings
    levelMatching: dict[str, Any] | None = None

    # Genre override
    genre_override: str | None = None


class ProcessRequest(BaseModel):
    """Request to process audio"""
    input_path: str
    settings: ProcessingSettings
    reference_path: str | None = None


class ProcessResponse(BaseModel):
    """Response after submitting processing job"""
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Job status response"""
    job_id: str
    status: str
    progress: float
    error_message: str | None = None
    result_data: dict[str, Any] | None = None


@router.post("/process", response_model=ProcessResponse)
async def process_audio(request: ProcessRequest) -> ProcessResponse:
    """
    Submit an audio file for processing.
    Returns a job ID that can be used to track progress.
    """
    if not _processing_engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    try:
        # Validate input path against allowed directories (#2559)
        try:
            validated_input = validate_file_path(request.input_path)
        except PathValidationError as e:
            raise HTTPException(status_code=400, detail=f"Invalid input path: {e}")

        validated_reference: Path | None = None
        if request.reference_path:
            try:
                validated_reference = validate_file_path(request.reference_path)
            except PathValidationError as e:
                raise HTTPException(status_code=400, detail=f"Invalid reference path: {e}")

        # Create processing job
        job = _processing_engine.create_job(
            input_path=str(validated_input),
            settings=request.settings.model_dump(),
            mode=request.settings.mode,
            reference_path=str(validated_reference) if validated_reference else None
        )

        # Submit to queue
        try:
            job_id = await _processing_engine.submit_job(job)
        except asyncio.QueueFull:
            raise HTTPException(
                status_code=503,
                detail="Processing queue is full, please try again later",
            )

        logger.info(f"Processing job {job_id} submitted for {request.input_path}")

        return ProcessResponse(
            job_id=job_id,
            status="queued",
            message="Processing job submitted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit processing job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-and-process", response_model=ProcessResponse)
async def upload_and_process(
    file: UploadFile = File(...),
    settings: str = Form(...)  # JSON string of ProcessingSettings
) -> ProcessResponse:
    """
    Upload an audio file and immediately submit for processing.
    Combines file upload and processing submission in one request.
    """
    if not _processing_engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    try:
        # Parse settings from JSON string
        import json
        settings_dict = json.loads(settings)
        processing_settings = ProcessingSettings(**settings_dict)

        # Save uploaded file to temp location
        temp_dir = Path(tempfile.gettempdir()) / "auralis_uploads"
        temp_dir.mkdir(exist_ok=True)

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

        # Use a UUID filename to prevent client-controlled path injection (#2560)
        original_ext = Path(file.filename or "").suffix.lower()
        if original_ext not in _ALLOWED_AUDIO_EXTENSIONS:
            original_ext = ".bin"
        input_path = temp_dir / f"{uuid.uuid4()}{original_ext}"
        with open(input_path, "wb") as f:
            f.write(content)

        logger.info(f"Uploaded file saved to {input_path}")

        # Create and submit job
        job = _processing_engine.create_job(
            input_path=str(input_path),
            settings=processing_settings.model_dump(),
            mode=processing_settings.mode
        )

        try:
            job_id = await _processing_engine.submit_job(job)
        except asyncio.QueueFull:
            raise HTTPException(
                status_code=503,
                detail="Processing queue is full, please try again later",
            )

        return ProcessResponse(
            job_id=job_id,
            status="queued",
            message=f"File {file.filename} uploaded and queued for processing"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload and process: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get the status of a processing job"""
    if not _processing_engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    job = _processing_engine.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        error_message=job.error_message,
        result_data=job.result_data
    )


@router.get("/job/{job_id}/download")
async def download_result(job_id: str) -> FileResponse:
    """
    Download the processed audio file.
    Only available when job status is 'completed'.
    """
    if not _processing_engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    job = _processing_engine.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != ProcessingStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Job not completed (status: {job.status.value})")

    output_path = Path(job.output_path).resolve()

    # Validate output path is within the expected temp directory (#2561)
    allowed_output_base = Path(tempfile.gettempdir()).resolve()
    try:
        output_path.relative_to(allowed_output_base)
    except ValueError:
        logger.error(f"Job {job_id} output path outside expected directory: {output_path}")
        raise HTTPException(status_code=500, detail="Output path configuration error")

    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    # Determine media type based on file extension
    media_types = {
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".mp3": "audio/mpeg",
    }
    media_type = media_types.get(output_path.suffix, "application/octet-stream")

    return FileResponse(
        path=str(output_path),
        media_type=media_type,
        filename=f"auralis_processed{output_path.suffix}"
    )


@router.post("/job/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    """Cancel a queued or processing job"""
    if not _processing_engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    success = _processing_engine.cancel_job(job_id)
    if not success:
        # Check if job exists to provide correct error
        job = _processing_engine.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=400, detail="Job cannot be cancelled (already completed)")

    return {"message": "Job cancelled successfully", "job_id": job_id}


@router.get("/jobs")
async def list_jobs(status: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List all processing jobs, optionally filtered by status"""
    if not _processing_engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    jobs = _processing_engine.get_all_jobs()

    # Filter by status if provided
    if status:
        try:
            status_enum = ProcessingStatus(status)
            jobs = [j for j in jobs if j.status == status_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    # Limit results
    jobs = jobs[:limit]

    return {
        "jobs": [job.to_dict() for job in jobs],
        "total": len(jobs)
    }


@router.get("/queue/status")
async def get_queue_status() -> dict[str, Any]:
    """Get current processing queue status"""
    if not _processing_engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    return _processing_engine.get_queue_status()


@router.get("/presets")
async def get_processing_presets() -> dict[str, Any]:
    """Get available processing presets"""
    presets = {
        "adaptive": {
            "name": "Adaptive Mastering",
            "description": "Intelligent content-aware mastering without reference",
            "mode": "adaptive",
            "settings": {
                "eq": {"enabled": True},
                "dynamics": {"enabled": True},
                "levelMatching": {"enabled": True, "targetLufs": -16}
            }
        },
        "gentle": {
            "name": "Gentle Enhancement",
            "description": "Subtle improvements preserving original character",
            "mode": "adaptive",
            "settings": {
                "eq": {
                    "enabled": True,
                    "low": 1,
                    "lowMid": 0.5,
                    "mid": 0,
                    "highMid": 1,
                    "high": 2
                },
                "dynamics": {
                    "enabled": True,
                    "compressor": {
                        "threshold": -24,
                        "ratio": 2,
                        "attack": 10,
                        "release": 200
                    }
                }
            }
        },
        "warm": {
            "name": "Warm & Rich",
            "description": "Enhanced low end with warm mid range",
            "mode": "adaptive",
            "settings": {
                "eq": {
                    "enabled": True,
                    "low": 2,
                    "lowMid": 1,
                    "mid": -0.5,
                    "highMid": 0,
                    "high": 1
                },
                "dynamics": {
                    "enabled": True,
                    "compressor": {
                        "threshold": -20,
                        "ratio": 3,
                        "attack": 5,
                        "release": 150
                    }
                }
            }
        },
        "bright": {
            "name": "Bright & Crisp",
            "description": "Enhanced clarity and presence",
            "mode": "adaptive",
            "settings": {
                "eq": {
                    "enabled": True,
                    "low": -1,
                    "lowMid": 0,
                    "mid": 1,
                    "highMid": 2,
                    "high": 3
                },
                "dynamics": {
                    "enabled": True,
                    "compressor": {
                        "threshold": -16,
                        "ratio": 4,
                        "attack": 1,
                        "release": 50
                    }
                }
            }
        },
        "punchy": {
            "name": "Punchy & Dynamic",
            "description": "Strong bass and aggressive dynamics",
            "mode": "adaptive",
            "settings": {
                "eq": {
                    "enabled": True,
                    "low": 3,
                    "lowMid": 1,
                    "mid": 0,
                    "highMid": 1,
                    "high": 2
                },
                "dynamics": {
                    "enabled": True,
                    "compressor": {
                        "threshold": -12,
                        "ratio": 6,
                        "attack": 0.5,
                        "release": 30
                    }
                }
            }
        }
    }

    return {"presets": presets}


@router.delete("/jobs/cleanup")
async def cleanup_old_jobs(max_age_hours: int = 24) -> dict[str, Any]:
    """Clean up completed jobs older than specified hours"""
    if not _processing_engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    removed_count = await _processing_engine.cleanup_old_jobs(max_age_hours)

    return {
        "message": f"Cleaned up jobs older than {max_age_hours} hours",
        "removed": removed_count
    }