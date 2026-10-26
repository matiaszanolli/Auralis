"""
Files Router
~~~~~~~~~~~~

Handles file operations: file uploads and supported format queries.

Endpoints:
- POST /api/files/upload - Upload audio files
- GET /api/audio/formats - Get supported audio formats

Note: POST /api/library/scan is handled exclusively by routers/library.py
which supports multiple directories, recursive scanning, and progress callbacks
via WebSocket (fixes #2123).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, Depends




# Upload limits — single source of truth in config.limits (#4033). MAX_UPLOAD_FILES
# bounds how many files one multipart request may carry so a single request can't
# monopolise the backend / bloat the DB (#4349); MAX_UPLOAD_BYTES is the per-file
# byte cap enforced at the read site below.
from .files_models import SupportedFormatsResponse, UploadResultResponse
from .files_deps import _repo_deps
from .files_upload import (
    upload_files,
)


logger = logging.getLogger(__name__)


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_files_router() used to be a closure: both handlers below were nested
# inside it purely to reach get_repository_factory via closure capture, which
# made a handler impossible to import or call without first building the whole
# router. Handlers are now module level; they reach the same callables through
# FastAPI Depends() instead.
#
# Factory calls can coexist in one process (the live app plus throwaway test
# apps), so each router publishes its own deps through a request ContextVar.
# The module-level holder is only the fallback for direct handler calls where
# no router-level dependency ran (#5262).
#
# A handler's Depends() default is only consulted when FastAPI itself invokes
# it for a real request; a direct unit-test call passes the dependency
# explicitly as a keyword argument and never touches _repo_deps at all --
# that's the seam #4670 asked for.
# ============================================================================


async def get_supported_formats() -> dict[str, Any]:
    """
    Get supported audio formats.

    Returns information about supported input/output formats,
    sample rates, and bit depths.

    Returns:
        dict: Supported formats, sample rates, and bit depths
    """
    # #4768: these used to be hand-typed literals that had drifted — input
    # omitted .aiff/.aif/.au/.wma/.opus, all of which the upload validator in
    # this same file accepts. Derive each list from what actually enforces it.
    from typing import get_args

    from auralis.io.formats import SUPPORTED_FORMATS

    # What ProcessingSettings will accept for a processing job. Not every
    # (format, bit_depth) pair is valid — its model validator rejects the ones
    # libsndfile cannot write — so these are the options, not a matrix.
    #
    # routes.py treats the processing router as optional and tolerates it
    # failing to import. When it cannot, no processing job can be submitted,
    # so the truthful answer is "no output formats", not a crash here.
    try:
        from routers.processing_api import ProcessingSettings
    except Exception:
        output_formats: list[str] = []
        bit_depths: list[int] = []
    else:
        fields = ProcessingSettings.model_fields
        output_formats = sorted(f".{fmt}" for fmt in get_args(fields["output_format"].annotation))
        bit_depths = sorted(get_args(fields["bit_depth"].annotation))

    return {
        # The decoder's single source of truth (#4109), same set upload uses.
        "input_formats": sorted(SUPPORTED_FORMATS),
        "output_formats": output_formats,
        "sample_rates": [44100, 48000, 88200, 96000, 192000],
        "bit_depths": bit_depths,
    }


def create_files_router(
    get_repository_factory: Callable[[], Any] | None = None
) -> APIRouter:
    """
    Factory function to create files router with dependencies.

    Args:
        get_repository_factory: Callable that returns RepositoryFactory instance

    Returns:
        APIRouter: Configured router instance

    Note:
        Directory scanning is handled by routers/library.py (fixes #2123).
    """
    router = APIRouter(
        tags=["files"],
        dependencies=[Depends(_repo_deps.bind(get_repository_factory))],
    )

    router.add_api_route("/api/files/upload", upload_files, methods=["POST"], response_model=UploadResultResponse)
    router.add_api_route("/api/audio/formats", get_supported_formats, methods=["GET"], response_model=SupportedFormatsResponse)

    return router
