"""POST /api/files/upload takes duration / rate / channels from the header (#5962).

It decoded each whole upload with load_audio() (up to the multi-GiB decode budget) just to
read three numbers, while holding both the upload bytes and the decoded array.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf
from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.files import create_files_router  # noqa: E402


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))  # uploads land in tmp
    repos = Mock()
    repos.tracks.add = Mock(side_effect=lambda info: Mock(
        id=7, title=info["title"], duration=info["duration"], sample_rate=info["sample_rate"],
    ))
    app = FastAPI()
    app.include_router(create_files_router(get_repository_factory=lambda: repos))
    return TestClient(app), repos, tmp_path


def _wav_bytes(tmp_path, seconds=2, rate=22050, channels=2):
    path = tmp_path / "src.wav"
    sf.write(str(path), np.zeros((seconds * rate, channels), dtype="float32"), rate)
    return path.read_bytes()


def test_metadata_comes_from_the_header_without_decoding(api, monkeypatch):
    client, repos, tmp_path = api
    import auralis.io.unified_loader as loader

    monkeypatch.setattr(loader, "load_audio", Mock(side_effect=AssertionError("decoded the whole upload")))
    body = _wav_bytes(tmp_path)

    response = client.post("/api/files/upload", files=[("files", ("song.wav", body, "audio/wav"))])

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "success"
    sent = repos.tracks.add.call_args.args[0]
    assert sent["duration"] == pytest.approx(2.0)
    assert sent["sample_rate"] == 22050
    assert sent["channels"] == 2


def test_an_upload_whose_header_is_unreadable_is_an_error_not_a_track(api):
    client, repos, _ = api
    corrupt = b"RIFF\x00\x00\x00\x00WAVEjunkjunkjunk" + b"\x00" * 64

    response = client.post("/api/files/upload", files=[("files", ("bad.wav", corrupt, "audio/wav"))])

    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "error"
    repos.tracks.add.assert_not_called()
