"""
Uploads are bounded per request and on disk (#6167)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

200 files x 500 MB per request, repeated, filled the home volume. A request now has a total byte
budget and ~/.auralis/uploads a quota; a file past either gets a clear per-file error and nothing is
stored for it.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.files_upload_budget import UploadBudget, _directory_bytes


def test_the_request_budget_admits_until_the_total_would_be_exceeded():
    budget = UploadBudget(request_limit=100, directory_limit=10**9, directory=Path("/nonexistent"))

    assert budget.admit_request(60) is True
    assert budget.admit_request(40) is True  # exactly at the limit
    assert budget.admit_request(1) is False
    assert budget.admit_request(0) is True


def test_a_refused_file_is_not_counted_against_the_budget():
    budget = UploadBudget(request_limit=100, directory_limit=10**9, directory=Path("/nonexistent"))

    assert budget.admit_request(150) is False
    assert budget.admit_request(100) is True  # the refusal did not consume anything


def test_directory_size_counts_regular_files_and_tolerates_a_missing_directory(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"x" * 10)
    (tmp_path / "b.wav").write_bytes(b"x" * 5)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.wav").write_bytes(b"x" * 99)  # not counted: only direct files are uploads

    assert _directory_bytes(tmp_path) == 15
    assert _directory_bytes(tmp_path / "missing") == 0


async def test_storage_admission_uses_the_measured_size_and_tracks_new_files(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"x" * 60)
    budget = UploadBudget(request_limit=10**9, directory_limit=100, directory=tmp_path)

    assert await budget.admit_storage(40) is True
    budget.record_stored(40)
    assert await budget.admit_storage(1) is False  # 60 existing + 40 stored = at the quota


async def test_the_directory_is_measured_once_not_per_file(tmp_path, monkeypatch):
    calls = []
    real = _directory_bytes
    monkeypatch.setattr("routers.files_upload_budget._directory_bytes", lambda d: calls.append(d) or real(d))
    budget = UploadBudget(request_limit=10**9, directory_limit=10**9, directory=tmp_path)

    for _ in range(3):
        await budget.admit_storage(1)

    assert len(calls) == 1


# --- through the real route -------------------------------------------------------------------

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from unittest.mock import Mock  # noqa: E402

from routers.files import create_files_router  # noqa: E402


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    repos = Mock()
    repos.tracks.add = Mock(side_effect=lambda info: Mock(
        id=7, title=info["title"], duration=info["duration"], sample_rate=info["sample_rate"],
    ))
    app = FastAPI()
    app.include_router(create_files_router(get_repository_factory=lambda: repos))
    return TestClient(app), repos, tmp_path


def _wav(tmp_path) -> bytes:
    path = tmp_path / "src.wav"
    sf.write(str(path), np.zeros((4410, 2), dtype="float32"), 22050)
    return path.read_bytes()


def test_the_second_file_past_the_request_budget_is_refused_and_nothing_is_stored_for_it(api, monkeypatch):
    client, repos, tmp_path = api
    body = _wav(tmp_path)
    monkeypatch.setattr("routers.files_upload.MAX_UPLOAD_REQUEST_BYTES", len(body) + len(body) // 2)

    response = client.post("/api/files/upload", files=[
        ("files", ("a.wav", body, "audio/wav")),
        ("files", ("b.wav", body, "audio/wav")),
    ])

    first, second = response.json()["results"]
    assert first["status"] == "success"
    assert second["status"] == "error" and "budget" in second["message"]
    assert repos.tracks.add.call_count == 1
    assert len(list((tmp_path / ".auralis" / "uploads").iterdir())) == 1


def test_a_full_uploads_directory_refuses_the_file_with_a_clear_message(api, monkeypatch):
    client, repos, tmp_path = api
    body = _wav(tmp_path)
    uploads = tmp_path / ".auralis" / "uploads"
    uploads.mkdir(parents=True)
    (uploads / "existing.wav").write_bytes(b"x" * 1000)
    monkeypatch.setattr("routers.files_upload.MAX_UPLOAD_DIR_BYTES", 1000 + len(body) - 1)

    response = client.post("/api/files/upload", files=[("files", ("a.wav", body, "audio/wav"))])

    result = response.json()["results"][0]
    assert result["status"] == "error" and "storage is full" in result["message"]
    repos.tracks.add.assert_not_called()
    assert [p.name for p in uploads.iterdir()] == ["existing.wav"]
