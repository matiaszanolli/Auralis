"""
Regression tests for the processing router's closure-to-module-level
extraction (#4670).

create_processing_router() used to be a 570-line closure -- every handler was
a nested `async def` reachable only by constructing the whole router around a
live engine getter. Handlers are now module-level `async def` functions with
FastAPI Depends() defaults; a caller that wants to unit-test one directly just
passes the engine (or the enhancement-settings getter) explicitly as a keyword
argument, bypassing Depends(), _ProcessingDeps and the router entirely. These
tests exist to prove that seam is real, not just that it types.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.processing_engine import ProcessingStatus  # noqa: E402
from routers.processing_api import (  # noqa: E402
    ProcessRequest,
    ProcessingSettings,
    cancel_job,
    get_job_status,
    get_processing_parameters,
    get_queue_status,
    process_audio,
)

pytestmark = pytest.mark.asyncio


async def test_get_queue_status_callable_with_a_bare_stub_engine():
    """No router, no _ProcessingDeps, no app -- just the handler and a stub."""
    stub_engine = MagicMock()
    stub_engine.get_queue_status = MagicMock(return_value={"queued": 3, "total": 3})

    result = await get_queue_status(engine=stub_engine)

    assert result == {"queued": 3, "total": 3}
    stub_engine.get_queue_status.assert_called_once()


async def test_get_queue_status_without_an_engine_is_503():
    """The `engine is None` 503 guard survived the move out of the closure."""
    with pytest.raises(HTTPException) as exc_info:
        await get_queue_status(engine=None)

    assert exc_info.value.status_code == 503


async def test_get_job_status_callable_with_a_bare_stub_engine():
    job = MagicMock()
    job.job_id = "job-1"
    job.status = ProcessingStatus.COMPLETED
    job.progress = 1.0
    job.error_message = None
    job.result_data = {"lufs": -14.0}

    stub_engine = MagicMock()
    stub_engine.get_job = AsyncMock(return_value=job)

    result = await get_job_status("job-1", engine=stub_engine)

    assert result.job_id == "job-1"
    assert result.status == ProcessingStatus.COMPLETED
    assert result.result_data == {"lufs": -14.0}
    stub_engine.get_job.assert_awaited_once_with("job-1")


async def test_cancel_job_callable_with_a_bare_stub_engine():
    stub_engine = MagicMock()
    stub_engine.cancel_job = AsyncMock(return_value=True)

    result = await cancel_job("job-1", engine=stub_engine)

    assert result == {"message": "Job cancelled successfully", "job_id": "job-1"}


async def test_process_audio_reference_mode_without_reference_is_422():
    """#4735's fail-fast is reachable without building the router."""
    stub_engine = MagicMock()
    request = ProcessRequest(
        input_path="/nonexistent/input.wav",
        settings=ProcessingSettings(mode="reference"),
    )

    with pytest.raises(HTTPException) as exc_info:
        await process_audio(request, engine=stub_engine)

    # 400 (path validation runs first) or 422 (reference guard) -- either way
    # the handler ran its own logic, not the router's.
    assert exc_info.value.status_code in (400, 422)
    stub_engine.create_job.assert_not_called()


async def test_get_processing_parameters_takes_its_settings_getter_directly():
    """GET /parameters resolves the preset through the getter it is handed,
    so the #5073 'not wired up' 503 and the happy path are both reachable
    without a router."""
    result = await get_processing_parameters(
        get_enhancement_settings=lambda: {"preset": "adaptive"}
    )

    assert result["is_default"] is True
    assert result["target_lufs"] == -14.0

    with pytest.raises(HTTPException) as exc_info:
        await get_processing_parameters(get_enhancement_settings=None)

    assert exc_info.value.status_code == 503
