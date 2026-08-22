"""Direct unit tests for core.job_cleanup.cleanup_expired_jobs (#4250 follow-up).

cleanup_expired_jobs was extracted out of ProcessingEngine.cleanup_old_jobs
so the TTL-sweep logic is testable without constructing a full
ProcessingEngine. Behavioral coverage of the same semantics via
ProcessingEngine itself remains in test_processing_engine.py; this file
exercises the free function in isolation.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from core.job_cleanup import cleanup_expired_jobs  # noqa: E402
from core.job_models import ProcessingStatus  # noqa: E402


def _job(status: ProcessingStatus, completed_at, output_path: Path, input_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        completed_at=completed_at,
        output_path=str(output_path),
        input_path=str(input_path),
    )


@pytest.mark.asyncio
async def test_removes_expired_completed_job(tmp_path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    output_path = tmp_path / "out.wav"
    input_path = upload_dir / "in.wav"
    output_path.write_bytes(b"x")
    input_path.write_bytes(b"y")

    jobs = {
        "job-1": _job(
            ProcessingStatus.COMPLETED,
            datetime.now() - timedelta(hours=25),
            output_path,
            input_path,
        )
    }
    lock = asyncio.Lock()

    removed = await cleanup_expired_jobs(jobs, lock, {}, upload_dir, max_age_hours=24)

    assert removed == 1
    assert "job-1" not in jobs
    assert not output_path.exists()
    assert not input_path.exists()


@pytest.mark.asyncio
async def test_leaves_fresh_job_untouched(tmp_path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    jobs = {
        "job-1": _job(
            ProcessingStatus.COMPLETED,
            datetime.now(),
            tmp_path / "out.wav",
            upload_dir / "in.wav",
        )
    }
    lock = asyncio.Lock()

    removed = await cleanup_expired_jobs(jobs, lock, {}, upload_dir, max_age_hours=24)

    assert removed == 0
    assert "job-1" in jobs


@pytest.mark.asyncio
async def test_leaves_queued_and_processing_jobs_untouched_regardless_of_age(tmp_path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    old = datetime.now() - timedelta(hours=999)
    jobs = {
        "queued": _job(ProcessingStatus.QUEUED, None, tmp_path / "a.wav", upload_dir / "a-in.wav"),
        "processing": _job(ProcessingStatus.PROCESSING, None, tmp_path / "b.wav", upload_dir / "b-in.wav"),
        "completed-old": _job(ProcessingStatus.COMPLETED, old, tmp_path / "c.wav", upload_dir / "c-in.wav"),
    }
    lock = asyncio.Lock()

    removed = await cleanup_expired_jobs(jobs, lock, {}, upload_dir, max_age_hours=0.0)

    assert removed == 1
    assert set(jobs) == {"queued", "processing"}


@pytest.mark.asyncio
async def test_input_file_outside_upload_dir_is_not_deleted(tmp_path):
    """A library track's input_path must survive cleanup — only files under
    upload_dir (uploaded-for-processing temp files) are eligible (#3327)."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    library_input = tmp_path / "library" / "track.flac"
    library_input.parent.mkdir()
    library_input.write_bytes(b"z")
    output_path = tmp_path / "out.wav"
    output_path.write_bytes(b"x")

    jobs = {
        "job-1": _job(
            ProcessingStatus.COMPLETED,
            datetime.now() - timedelta(hours=25),
            output_path,
            library_input,
        )
    }
    lock = asyncio.Lock()

    removed = await cleanup_expired_jobs(jobs, lock, {}, upload_dir, max_age_hours=24)

    assert removed == 1
    assert not output_path.exists()
    assert library_input.exists()  # not deleted — outside upload_dir


@pytest.mark.asyncio
async def test_progress_callbacks_removed_with_expired_job(tmp_path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    jobs = {
        "job-1": _job(
            ProcessingStatus.COMPLETED,
            datetime.now() - timedelta(hours=25),
            tmp_path / "out.wav",
            upload_dir / "in.wav",
        )
    }
    progress_callbacks = {"job-1": [lambda *_: None]}
    lock = asyncio.Lock()

    removed = await cleanup_expired_jobs(jobs, lock, progress_callbacks, upload_dir, max_age_hours=24)

    assert removed == 1
    assert "job-1" not in progress_callbacks


@pytest.mark.asyncio
async def test_missing_files_do_not_raise(tmp_path):
    """Neither output nor input file exists on disk — unlink(missing_ok=True)
    must swallow this rather than raising."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    jobs = {
        "job-1": _job(
            ProcessingStatus.FAILED,
            datetime.now() - timedelta(hours=25),
            tmp_path / "never-existed.wav",
            upload_dir / "never-existed-in.wav",
        )
    }
    lock = asyncio.Lock()

    removed = await cleanup_expired_jobs(jobs, lock, {}, upload_dir, max_age_hours=24)

    assert removed == 1
