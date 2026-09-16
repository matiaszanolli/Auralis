"""
Processing API Routes
~~~~~~~~~~~~~~~~~~~~~

FastAPI routes for audio processing functionality.

Split by sub-resource (#5472). This module holds path-based job submission
(POST /process, whose validate_file_path tests patch on this module) and
create_processing_router(), which registers every /api/processing route;
every handler and model is re-exported here so
`from routers.processing_api import X` keeps working.
- processing_models.py      request/response bodies
- processing_upload.py      upload-and-process and its upload helpers
- processing_deps.py        Depends() providers and per-router binding (#4670)
- processing_jobs.py        job status, download, cancel, list, queue, cleanup
- processing_parameters.py  presets and live mastering parameters

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Re-exported upload allowlist (defined for processing_upload.py; tests read it here).
from auralis.io.formats import (  # noqa: F401
    AUDIO_EXTENSIONS as _ALLOWED_AUDIO_EXTENSIONS,
)
from fastapi import APIRouter, Depends, HTTPException

from core.processing_engine import ProcessingEngine, ProcessingStatus
from security.path_security import PathValidationError, validate_file_path

from .dependencies import with_error_handling
from .processing_deps import (
    _deps,
    _get_processing_engine,
    _make_deps_binder,
    _ProcessingDeps,
)
from .processing_jobs import (
    cancel_job,
    cleanup_old_jobs,
    download_result,
    get_job_status,
    get_queue_status,
    list_jobs,
)
from .processing_models import (  # noqa: F401
    CancelJobResponse,
    CleanupResponse,
    JobListResponse,
    JobStatusResponse,
    PresetsResponse,
    ProcessingParametersResponse,
    ProcessingSettings,
    ProcessRequest,
    ProcessResponse,
    QueueStatusResponse,
)
from .processing_parameters import (
    get_processing_parameters,
    get_processing_presets,
)

# Re-exported: tests import the upload allowlist and magic sniff from here.
from .processing_upload import (
    _is_valid_audio_magic,  # noqa: F401
    upload_and_process,
)

logger = logging.getLogger(__name__)


@with_error_handling("submit processing job")
async def process_audio(
    request: ProcessRequest,
    engine: ProcessingEngine | None = Depends(_get_processing_engine),
) -> ProcessResponse:
    """
    Submit an audio file for processing.
    Returns a job ID that can be used to track progress.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Processing engine not available")

    # Validate input path against allowed directories (#2559)
    try:
        validated_input = validate_file_path(
            request.input_path, context="input_path"
        )
    except PathValidationError:
        # validate_file_path logs it once with the context above (#4925).
        raise HTTPException(status_code=400, detail="Invalid or inaccessible input path")

    # A reference or hybrid job with no reference is not a meaningful
    # adaptive fallback — the caller asked for their reference to be matched.
    # Fail fast and say so, rather than silently returning adaptive-mastered
    # audio labelled as a reference job (#4735; hybrid too since #5058).
    if request.settings.requires_reference and not request.reference_path:
        raise HTTPException(
            status_code=422,
            detail=f"mode={request.settings.mode!r} requires a reference_path",
        )

    validated_reference: Path | None = None
    if request.reference_path:
        try:
            validated_reference = validate_file_path(
                request.reference_path, context="reference_path"
            )
        except PathValidationError:
            # validate_file_path logs it once with the context above (#4925).
            raise HTTPException(status_code=400, detail="Invalid or inaccessible reference path")

    # Create processing job
    job = await engine.create_job(
        input_path=str(validated_input),
        settings=request.settings.model_dump(),
        mode=request.settings.mode,
        reference_path=str(validated_reference) if validated_reference else None
    )

    # Submit to queue
    try:
        job_id = await engine.submit_job(job)
    except asyncio.QueueFull:
        raise HTTPException(
            status_code=503,
            detail="Processing queue is full, please try again later",
        )

    # Debug, not info (#3844): input_path is an absolute media-library path.
    logger.debug(f"Processing job {job_id} submitted for {request.input_path}")

    return ProcessResponse(
        job_id=job_id,
        status=ProcessingStatus.QUEUED,
        message="Processing job submitted successfully"
    )


def create_processing_router(
    get_processing_engine: Callable[[], ProcessingEngine | None],
    get_enhancement_settings: Callable[[], dict[str, Any]] | None = None,
) -> APIRouter:
    """
    Factory that assembles the processing router from the module-level
    handlers (this module and its siblings), wiring the engine getter in through Depends() rather than
    a closure (#4670). It keeps the factory shape every other router uses,
    which is what replaced the module-level mutable + ``set_processing_engine``
    setter this router started out with (fixes #3862 / BE-RH-11).

    Args:
        get_processing_engine: Callable returning the live ``ProcessingEngine``
            instance, or ``None`` if not yet initialised.
        get_enhancement_settings: Callable returning the live enhancement
            settings dict, used only by GET /parameters to resolve the active
            preset. Optional so existing callers/tests that don't touch that
            route need no changes; that route 503s if omitted (#5073).

    Returns:
        Configured ``APIRouter`` for ``/api/processing``.
    """
    deps = _ProcessingDeps(get_processing_engine, get_enhancement_settings)
    # Keep the module-level holder pointing at the most recent call, so
    # anything resolving outside a request still sees a wired-up getter.
    _deps.get_processing_engine = deps.get_processing_engine
    _deps.get_enhancement_settings = deps.get_enhancement_settings

    router = APIRouter(
        prefix="/api/processing",
        tags=["audio-processing"],
        dependencies=[Depends(_make_deps_binder(deps))],
    )

    router.add_api_route("/process", process_audio, methods=["POST"], response_model=ProcessResponse)
    router.add_api_route("/upload-and-process", upload_and_process, methods=["POST"], response_model=ProcessResponse)
    router.add_api_route("/job/{job_id}", get_job_status, methods=["GET"], response_model=JobStatusResponse)
    router.add_api_route("/job/{job_id}/download", download_result, methods=["GET"])
    router.add_api_route("/job/{job_id}/cancel", cancel_job, methods=["POST"], response_model=CancelJobResponse)
    router.add_api_route("/jobs", list_jobs, methods=["GET"], response_model=JobListResponse)
    router.add_api_route("/queue/status", get_queue_status, methods=["GET"], response_model=QueueStatusResponse)
    router.add_api_route("/presets", get_processing_presets, methods=["GET"], response_model=PresetsResponse)
    router.add_api_route("/parameters", get_processing_parameters, methods=["GET"], response_model=ProcessingParametersResponse)
    router.add_api_route("/jobs/cleanup", cleanup_old_jobs, methods=["DELETE"], response_model=CleanupResponse)

    return router
