"""Regression test for the multipart file-count cap (#4349).

upload_files capped each file at 500 MB but placed no limit on how many files a
single request may carry, so one multipart body with tens of thousands of tiny
valid-magic files could monopolise the backend and bloat the DB. The handler now
rejects a batch over _MAX_UPLOAD_FILES with 413 before decoding anything.

Self-contained (builds the router via create_files_router) because the
main.library_manager-patching harness in test_files_api.py is pre-existing broken.
"""

import io
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.files import create_files_router, _MAX_UPLOAD_FILES  # noqa: E402


def _client() -> TestClient:
    app = FastAPI()
    # A repo factory is unnecessary: the count check short-circuits before any
    # repository access.
    app.include_router(create_files_router(get_repository_factory=lambda: object()))
    return TestClient(app)


def test_too_many_files_rejected_with_413():
    client = _client()
    tiny = b"RIFF" + b"\x00" * 40
    files = [
        ("files", (f"t{i}.wav", io.BytesIO(tiny), "audio/wav"))
        for i in range(_MAX_UPLOAD_FILES + 1)
    ]
    resp = client.post("/api/files/upload", files=files)

    assert resp.status_code == 413
    # Rejected up front — no per-file results were produced.
    assert "results" not in resp.json()


def test_batch_at_the_ceiling_is_not_count_rejected():
    # Exactly _MAX_UPLOAD_FILES must pass the count gate (it may still 503 later
    # because there's no real repository, but it must NOT be a 413 count rejection).
    client = _client()
    tiny = b"RIFF" + b"\x00" * 40
    files = [
        ("files", (f"t{i}.wav", io.BytesIO(tiny), "audio/wav"))
        for i in range(_MAX_UPLOAD_FILES)
    ]
    resp = client.post("/api/files/upload", files=files)

    assert resp.status_code != 413
