"""Clearing caches works without the streamlined manager and reports real file counts (#6002).

Both clear endpoints required the manager (503 once the worker died, which nulls it), though the
chunk directory is what actually serves. The per-track clear returned tier entries (always 0 in
production) instead of the files it deleted, and left the track's recommendations and mastering
target entry behind.
"""

import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from cache import StreamlinedCacheManager  # noqa: E402
from config.limits import chunk_cache_dir  # noqa: E402
from core import mastering_target_service as mts  # noqa: E402
from routers.cache_streamlined import create_streamlined_cache_router  # noqa: E402


@pytest.fixture
def chunk_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    directory = chunk_cache_dir()
    directory.mkdir(parents=True)
    return directory


def _client(tmp_path, manager):
    app = FastAPI()
    app.include_router(create_streamlined_cache_router(
        get_cache_manager=lambda: manager,
        get_artwork_cache_dir=lambda: tmp_path / "artwork",
    ))
    return TestClient(app)




def test_clear_all_without_the_manager_still_sweeps_the_chunk_directory(tmp_path, chunk_dir):
    chunk = chunk_dir / "track_1_sig_adaptive_1.0_0.wav"
    chunk.write_bytes(b"wav")

    response = _client(tmp_path, None).post("/api/cache/clear")

    assert response.status_code == 200
    assert not chunk.exists()


def test_track_clear_without_the_manager_reports_the_files_it_deleted(tmp_path, chunk_dir):
    mine = [chunk_dir / f"track_7_sig_adaptive_1.0_{i}.wav" for i in range(3)]
    other = chunk_dir / "track_70_sig_adaptive_1.0_0.wav"
    for path in (*mine, other):
        path.write_bytes(b"wav")

    response = _client(tmp_path, None).delete("/api/cache/track/7")

    assert response.status_code == 200
    assert response.json()["removed"] == 3  # files, not tier entries
    assert not any(p.exists() for p in mine)
    assert other.exists()


def test_track_clear_with_the_manager_reports_files_and_drops_recommendations(tmp_path, chunk_dir):
    manager = StreamlinedCacheManager()
    manager.chunk_dir = chunk_dir
    for i in range(2):
        (chunk_dir / f"track_7_sig_adaptive_1.0_{i}.wav").write_bytes(b"wav")
    manager.mastering_recommendations[(7, 0.5)] = (1e18, {"x": 1})
    manager.mastering_recommendations[(8, 0.5)] = (1e18, {"x": 2})

    response = _client(tmp_path, manager).delete("/api/cache/track/7")

    assert response.json()["removed"] == 2
    assert list(manager.mastering_recommendations) == [(8, 0.5)]


def test_track_clear_drops_that_tracks_mastering_target_entry(tmp_path, chunk_dir, monkeypatch):
    service = mts.MasteringTargetService()
    service.cache["fingerprint_7_sigA"] = "mine"
    service.cache["fingerprint_7_sigB"] = "mine too"
    service.cache["fingerprint_70_sigA"] = "other track"
    monkeypatch.setattr(mts, "_global_mastering_target_service", service)

    _client(tmp_path, None).delete("/api/cache/track/7")

    assert list(service.cache) == ["fingerprint_70_sigA"]


def test_stats_report_the_chunk_directory_that_serves_playback(tmp_path, chunk_dir):
    for i in range(3):
        (chunk_dir / f"track_1_sig_adaptive_1.0_{i}.wav").write_bytes(b"\x00" * 1024)

    data = _client(tmp_path, StreamlinedCacheManager()).get("/api/cache/stats").json()

    assert data["chunk_directory"]["files"] == 3
    assert data["chunk_directory"]["size_mb"] == pytest.approx(3 * 1024 / (1024 * 1024))
    assert data["chunk_directory"]["max_mb"] == 512
