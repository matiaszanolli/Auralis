"""/api/health reports whether the engine is actually up, not just importable (#4684).

HAS_AURALIS was a bare `True`, so `auralis_available` was true unconditionally —
including after a failed Auralis init rolled every component back to None, with
every data route returning 503. And the demo-mode branch it gates in startup
could never run.
"""

import asyncio
import logging
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.health import create_health_router  # noqa: E402


def _client(**kwargs) -> TestClient:
    app = FastAPI()
    app.include_router(create_health_router(**kwargs))
    return TestClient(app)


def test_rolled_back_startup_is_not_reported_available():
    resp = _client(HAS_AURALIS=True, get_library_database=lambda: None).get("/api/health")
    assert resp.status_code == 200  # still the liveness probe desktop/main.js waits on
    assert resp.json() == {"status": "healthy", "auralis_available": False,
                           "fingerprint_engine_available": True}


def test_fully_initialised_backend_is_healthy_and_available():
    resp = _client(HAS_AURALIS=True, get_library_database=lambda: object()).get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "auralis_available": True,
                           "fingerprint_engine_available": True}


def test_engine_not_importable_is_not_available_even_with_a_database():
    resp = _client(HAS_AURALIS=False, get_library_database=lambda: object()).get("/api/health")
    assert resp.json()["auralis_available"] is False


def test_a_missing_fingerprint_engine_is_reported(monkeypatch):
    """#6107: without auralis_dsp every fingerprint and adaptive master fails."""
    import routers.health as health

    monkeypatch.setattr(health, "fingerprint_engine_error", lambda: "No module named 'auralis_dsp'")
    resp = _client(HAS_AURALIS=True, get_library_database=lambda: object()).get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["fingerprint_engine_available"] is False


def test_the_database_is_read_live_on_each_request():
    state = {"db": None}
    client = _client(HAS_AURALIS=True, get_library_database=lambda: state["db"])
    assert client.get("/api/health").json()["auralis_available"] is False
    state["db"] = object()
    assert client.get("/api/health").json()["auralis_available"] is True


def test_demo_mode_branch_is_reachable(caplog):
    from config.startup import _init_auralis_components

    globals_dict: dict = {}
    with caplog.at_level(logging.WARNING, logger="config.startup"):
        asyncio.run(_init_auralis_components(False, False, None, globals_dict))

    assert any("demo mode" in r.message for r in caplog.records)
    assert globals_dict == {}  # nothing initialised


@pytest.mark.parametrize(
    ("database", "player", "fingerprint_error", "expected"),
    [
        (True, True, None, 200),
        (False, True, None, 503),
        (True, False, None, 503),
        (True, True, "Native DSP unavailable", 503),
    ],
)
def test_readiness_requires_initialized_components(monkeypatch, database, player, fingerprint_error, expected):
    import routers.health as health

    monkeypatch.setenv("AURALIS_LAUNCH_ID", "test-launch")
    monkeypatch.setattr(health, "fingerprint_engine_error", lambda: fingerprint_error)
    client = _client(
        HAS_AURALIS=True,
        get_library_database=lambda: object() if database else None,
        get_player_state_manager=lambda: object() if player else None,
    )
    assert client.get("/api/health").status_code == 200
    response = client.get("/api/ready")
    assert response.status_code == expected
    assert response.json() == {"ready": expected == 200}
    assert response.headers["X-Auralis-Launch-Id"] == "test-launch"
