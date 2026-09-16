"""
Processing Job Endpoints

Job status, download, cancel, listing, queue status and cleanup under
/api/processing. Split out of routers/processing_api.py (#5472), whose
create_processing_router() registers them.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, Query
from fastapi.responses import FileResponse

from core.processing_engine import ProcessingEngine, ProcessingJob, ProcessingStatus

from .dependencies import with_error_handling
from .errors import NotFoundError
from .processing_deps import _get_processing_engine
from .processing_models import JobListResponse, JobStatusResponse

logger = logging.getLogger(__name__)


def _job_status_response(job: ProcessingJob) -> JobStatusResponse:
    """Serialize one job identically for the detail and list endpoints."""
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        result_data=job.result_data,
    )


@with_error_handling("get job status")
async def get_job_status(
    job_id: str,
    engine: ProcessingEngine | None = Depends(_get_processing_engine),
) -> JobStatusResponse:
    """Get the status of a processing job"""
    if not engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    job = await engine.get_job(job_id)
    if not job:
        raise NotFoundError("Job")

    return _job_status_response(job)


@with_error_handling("download job result")
async def download_result(
    job_id: str,
    engine: ProcessingEngine | None = Depends(_get_processing_engine),
) -> FileResponse:
    """
    Download the processed audio file.
    Only available when job status is 'completed'.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    job = await engine.get_job(job_id)
    if not job:
        raise NotFoundError("Job")

    if job.status != ProcessingStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Job not completed (status: {job.status.value})")

    # A job that reached COMPLETED without output_path set is an
    # engine-layer bug, not a client error — but Path(None) raises an
    # unhandled TypeError rather than a typed response (#4736).
    if not job.output_path:
        logger.error(f"Job {job_id} is COMPLETED but has no output_path set")
        raise HTTPException(status_code=500, detail="Job completed but produced no output file")

    output_path = Path(job.output_path).resolve()

    # Validate output path is within the expected temp directory (#2561)
    allowed_output_base = Path(tempfile.gettempdir()).resolve()
    try:
        output_path.relative_to(allowed_output_base)
    except ValueError:
        logger.error(f"Job {job_id} output path outside expected directory: {output_path}")
        raise HTTPException(status_code=500, detail="Output path configuration error")

    if not output_path.exists():
        raise NotFoundError("Output file")

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


@with_error_handling("cancel job")
async def cancel_job(
    job_id: str,
    engine: ProcessingEngine | None = Depends(_get_processing_engine),
) -> dict[str, Any]:
    """Cancel a queued or processing job"""
    if not engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    success = await engine.cancel_job(job_id)
    if not success:
        # Check if job exists to provide correct error
        job = await engine.get_job(job_id)
        if not job:
            raise NotFoundError("Job")
        raise HTTPException(status_code=400, detail="Job cannot be cancelled (already completed)")

    return {"message": "Job cancelled successfully", "job_id": job_id}


@with_error_handling("list jobs")
async def list_jobs(
    status: ProcessingStatus | None = None,
    limit: int = Query(50, ge=1, le=1000),
    engine: ProcessingEngine | None = Depends(_get_processing_engine),
) -> JobListResponse:
    """List all processing jobs, optionally filtered by status.

    `status` is the enum rather than `str` + a hand-rolled check (#3896):
    FastAPI now rejects an unknown value at the boundary with 422, matching
    how `limit` already behaves, and OpenAPI documents the valid values.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    jobs = engine.get_all_jobs()

    # Filter by status if provided. FastAPI has already coerced and
    # validated the value, so no manual membership check is needed.
    if status:
        jobs = [j for j in jobs if j.status == status]

    total = len(jobs)
    limited_jobs = jobs[:limit]

    return JobListResponse(
        jobs=[_job_status_response(job) for job in limited_jobs],
        total=total,
    )


@with_error_handling("get queue status")
async def get_queue_status(
    engine: ProcessingEngine | None = Depends(_get_processing_engine),
) -> dict[str, Any]:
    """Get current processing queue status"""
    if not engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    return engine.get_queue_status()


async def cleanup_old_jobs(
    max_age_hours: float = Query(24, gt=0),
    engine: ProcessingEngine | None = Depends(_get_processing_engine),
) -> dict[str, Any]:
    """Clean up completed jobs older than specified hours"""
    if not engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    removed_count = await engine.cleanup_old_jobs(max_age_hours)

    return {
        "message": f"Cleaned up jobs older than {max_age_hours} hours",
        "removed": removed_count
    }
