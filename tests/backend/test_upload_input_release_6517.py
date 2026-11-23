"""upload-and-process inputs are bounded on disk and released when their job fails (#6517).

Each upload (up to 500 MB) was written to ``<tmp>/auralis_uploads`` with no
directory budget, and a FAILED or CANCELLED job kept it until the 1 h TTL sweep.
The route now checks an ``UploadBudget`` for that directory, and the job's input
is deleted as soon as the job ends failed or cancelled.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.job_cleanup import discard_upload_input, upload_temp_dir  # noqa: E402
from core.job_models import ProcessingJob, ProcessingStatus  # noqa: E402
from core.processing_engine import ProcessingEngine  # noqa: E402
from routers import processing_upload  # noqa: E402
from routers.processing_api import create_processing_router  # noqa: E402


@pytest.fixture
def uploads(tmp_path):
    """Point the temp dir at tmp_path; return the uploads dir inside it."""
    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        directory = upload_temp_dir()
        directory.mkdir()
        yield directory


def _job(input_path: Path, status: ProcessingStatus) -> ProcessingJob:
    job = ProcessingJob(job_id="job-1", input_path=str(input_path), output_path=str(input_path) + ".out",
                        settings={}, mode="adaptive")
    job.status = status
    return job


def _upload(directory: Path, name: str = "in.wav") -> Path:
    path = directory / name
    path.write_bytes(b"RIFF" + b"\0" * 100)
    return path


@pytest.mark.parametrize("status", [ProcessingStatus.FAILED, ProcessingStatus.CANCELLED])
def test_a_failed_or_cancelled_jobs_upload_is_deleted(uploads, status):
    path = _upload(uploads)
    discard_upload_input(_job(path, status))
    assert not path.exists()


@pytest.mark.parametrize("status", [ProcessingStatus.COMPLETED, ProcessingStatus.PROCESSING, ProcessingStatus.QUEUED])
def test_any_other_jobs_upload_is_kept(uploads, status):
    path = _upload(uploads)
    discard_upload_input(_job(path, status))
    assert path.exists()


def test_an_input_outside_the_uploads_dir_is_never_touched(uploads, tmp_path):
    library_track = tmp_path / "library" / "track.wav"
    library_track.parent.mkdir()
    library_track.write_bytes(b"audio")
    discard_upload_input(_job(library_track, ProcessingStatus.FAILED))
    assert library_track.exists()


@pytest.mark.asyncio
async def test_a_job_that_fails_releases_its_upload(uploads):
    engine = ProcessingEngine(max_concurrent_jobs=1)
    path = _upload(uploads)
    job = await engine.create_job(input_path=str(path), settings={})
    engine._prepare_job = AsyncMock(side_effect=RuntimeError("cannot decode"))  # type: ignore[method-assign]

    await engine.process_job(job)

    assert job.status == ProcessingStatus.FAILED
    assert not path.exists()


@pytest.mark.asyncio
async def test_cancelling_a_queued_job_releases_its_upload_at_once(uploads):
    engine = ProcessingEngine(max_concurrent_jobs=1)
    path = _upload(uploads)
    job = await engine.create_job(input_path=str(path), settings={})

    assert await engine.cancel_job(job.job_id)

    assert job.status == ProcessingStatus.CANCELLED
    assert not path.exists()


@pytest.mark.asyncio
async def test_cancelling_a_running_job_leaves_the_input_to_its_own_exit(uploads):
    engine = ProcessingEngine(max_concurrent_jobs=1)
    path = _upload(uploads)
    job = await engine.create_job(input_path=str(path), settings={})
    job.status = ProcessingStatus.PROCESSING  # its decode may still hold the file open

    assert await engine.cancel_job(job.job_id)

    assert path.exists()


@pytest.mark.asyncio
async def test_a_cancelled_job_reaching_the_worker_releases_its_upload(uploads):
    engine = ProcessingEngine(max_concurrent_jobs=1)
    path = _upload(uploads)
    job = await engine.create_job(input_path=str(path), settings={})
    job.status = ProcessingStatus.CANCELLED

    await engine.process_job(job)

    assert not path.exists()


def test_upload_is_refused_with_413_once_the_directory_budget_is_spent(uploads):
    engine = Mock(spec=ProcessingEngine)
    engine.create_job = AsyncMock()
    app = FastAPI()
    app.include_router(create_processing_router(lambda: engine))
    _upload(uploads, "queued.wav")  # 104 bytes already waiting

    with patch.object(processing_upload, "MAX_PROCESSING_UPLOAD_DIR_BYTES", 150):
        response = TestClient(app).post(
            "/api/processing/upload-and-process",
            files={"file": ("new.wav", io.BytesIO(b"RIFF" + b"\0" * 100), "audio/wav")},
            data={"settings": json.dumps({"mode": "adaptive"})},
        )

    assert response.status_code == 413
    assert sorted(p.name for p in uploads.iterdir()) == ["queued.wav"]
    engine.create_job.assert_not_called()
