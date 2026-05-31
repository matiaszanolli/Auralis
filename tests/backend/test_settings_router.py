"""
Settings router tests
~~~~~~~~~~~~~~~~~~~~~~

Regression coverage for the typed ``PUT /api/settings`` body (#3837 / BE-SCH-2).

Before the fix, the endpoint accepted ``updates: dict[str, Any]`` so a misspelled
field name silently no-op'd through the SettingsRepository whitelist (200 OK, no
change applied) and OpenAPI advertised "any object". The endpoint now takes a
typed ``SettingsUpdateRequest`` with ``extra='forbid'`` so unknown/out-of-range
fields are rejected with HTTP 422, and only fields the client actually sent are
forwarded to the repository (``exclude_unset``).
"""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# conftest already inserts auralis-web/backend on sys.path; keep this defensive
# so the module imports standalone too.
_BACKEND = str(Path(__file__).resolve().parent.parent.parent / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.settings import create_settings_router  # noqa: E402


_DEFAULT_SETTINGS = {
    "id": 1,
    "scan_folders": [],
    "file_types": ["mp3", "flac"],
    "auto_scan": False,
    "scan_interval": 3600,
    "crossfade_enabled": False,
    "crossfade_duration": 5.0,
    "gapless_enabled": True,
    "replay_gain_enabled": False,
    "volume": 0.8,
    "output_device": "default",
    "bit_depth": 16,
    "sample_rate": 44100,
    "theme": "dark",
    "language": "en",
    "show_visualizations": True,
    "mini_player_on_close": False,
    "default_preset": "adaptive",
    "auto_enhance": False,
    "enhancement_intensity": 1.0,
    "cache_size": 1024,
    "max_concurrent_scans": 4,
    "enable_analytics": False,
    "debug_mode": False,
    "created_at": None,
    "updated_at": None,
}


class _FakeSettings:
    def __init__(self, data: dict) -> None:
        self._data = data

    def to_dict(self) -> dict:
        return dict(self._data)


class _FakeSettingsRepo:
    """Records what reached the repository so tests can assert the request was
    (or was not) forwarded after validation."""

    def __init__(self) -> None:
        self.updated_with: dict | None = None

    def get_settings(self) -> _FakeSettings:
        return _FakeSettings(_DEFAULT_SETTINGS)

    def update_settings(self, payload: dict) -> _FakeSettings:
        self.updated_with = payload
        merged = {**_DEFAULT_SETTINGS, **payload}
        return _FakeSettings(merged)


@pytest.fixture()
def client() -> TestClient:
    repo = _FakeSettingsRepo()
    app = FastAPI()
    app.include_router(create_settings_router(lambda: repo))
    tc = TestClient(app)
    tc._repo = repo  # type: ignore[attr-defined]  # expose for assertions
    return tc


def test_update_settings_rejects_unknown_field(client: TestClient) -> None:
    """A misspelled/unknown field must 422, not silently no-op (the #3837 bug)."""
    resp = client.put("/api/settings", json={"volumee": 0.5})
    assert resp.status_code == 422
    assert client._repo.updated_with is None  # type: ignore[attr-defined]


def test_update_settings_validates_field_ranges(client: TestClient) -> None:
    """Out-of-range values are rejected with 422 (volume must be in [0, 1])."""
    resp = client.put("/api/settings", json={"volume": 2.0})
    assert resp.status_code == 422
    assert client._repo.updated_with is None  # type: ignore[attr-defined]


def test_update_settings_partial_excludes_unset(client: TestClient) -> None:
    """Only the fields the client sent reach the repo (exclude_unset)."""
    resp = client.put("/api/settings", json={"theme": "light"})
    assert resp.status_code == 200
    assert client._repo.updated_with == {"theme": "light"}  # type: ignore[attr-defined]
    assert resp.json()["settings"]["theme"] == "light"


def test_update_settings_accepts_multiple_known_fields(client: TestClient) -> None:
    """A multi-field valid update passes through unchanged."""
    resp = client.put(
        "/api/settings",
        json={"volume": 0.3, "crossfade_enabled": True, "scan_folders": ["/music"]},
    )
    assert resp.status_code == 200
    assert client._repo.updated_with == {  # type: ignore[attr-defined]
        "volume": 0.3,
        "crossfade_enabled": True,
        "scan_folders": ["/music"],
    }


def test_get_settings_returns_typed_shape(client: TestClient) -> None:
    """GET still works and is shaped by SettingsResponse."""
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["theme"] == "dark"
    assert body["volume"] == 0.8
