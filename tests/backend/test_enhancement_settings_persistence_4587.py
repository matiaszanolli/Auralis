"""
Regression tests: bidirectional enhancement-settings sync (#4587)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two independent desyncs, fixed together since they're the same "runtime dict
vs. persisted UserSettings" gap in opposite directions:

1. Settings -> runtime: PUT /api/settings (and POST /api/settings/reset)
   wrote to the DB but never re-seeded the live `enhancement_settings` dict
   or broadcast the change, so a Settings-dialog save only took effect at
   the next backend restart.
2. Runtime -> Settings: the enhancement router's toggle/preset/intensity
   endpoints mutated the runtime dict but never persisted, so an
   Enhancement Panel change was silently reverted by the next startup's
   `seed_enhancement_settings()` re-seed from the untouched DB row.

Mirrors the fixture patterns already established in
test_settings_router.py (direction 1) and test_preset_intensity_prewarm_4425.py
(direction 2) rather than inventing new ones.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = str(Path(__file__).resolve().parent.parent.parent / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.enhancement import create_enhancement_router  # noqa: E402
from routers.enhancement import _deps as _enhancement_deps  # noqa: E402
from routers.settings import create_settings_router  # noqa: E402

# routers/enhancement.py binds every handler to a MODULE-LEVEL `_deps`
# singleton (the "router-singleton test hazard" #5177 already tracks).
# create_enhancement_router() overwrites it with no teardown, so whichever
# call happens last "wins" for the rest of the pytest process — confirmed
# empirically: without this fixture, test_enhancement_api.py's
# TestGetMasteringRecommendation fails with an AttributeError against this
# file's own mock objects when both run in the same invocation. Snapshot/
# restore around every test here so this file's throwaway routers can never
# leak into a file that runs afterward. Not a fix for #5177 itself (a
# broader, separately-tracked hazard) — just this file staying isolated.
_ENHANCEMENT_DEPS_ATTRS = (
    "get_enhancement_settings", "connection_manager", "get_multi_tier_buffer",
    "get_player_state_manager", "get_repository_factory",
)


@pytest.fixture(autouse=True)
def _restore_enhancement_deps():
    snapshot = {attr: getattr(_enhancement_deps, attr, None) for attr in _ENHANCEMENT_DEPS_ATTRS}
    yield
    for attr, value in snapshot.items():
        setattr(_enhancement_deps, attr, value)


# ============================================================================
# Direction 1: PUT /api/settings / POST /api/settings/reset -> runtime dict
# ============================================================================

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


class _FakeSettingsRow:
    """Mimics the real UserSettings ORM object closely enough for
    seed_enhancement_settings(), which reads plain attributes via getattr()."""

    def __init__(self, data: dict) -> None:
        self._data = data
        for key, value in data.items():
            setattr(self, key, value)
        folders = data.get('scan_folders')
        self.scan_folders = json.dumps(folders) if folders else None

    def to_dict(self) -> dict:
        return dict(self._data)


class _FakeSettingsRepo:
    def __init__(self, initial: dict | None = None) -> None:
        self._current = dict(initial or _DEFAULT_SETTINGS)
        self.updated_with: dict | None = None

    def get_settings(self) -> _FakeSettingsRow:
        return _FakeSettingsRow(dict(self._current))

    def update_settings(self, payload: dict) -> _FakeSettingsRow:
        self.updated_with = payload
        self._current = {**self._current, **payload}
        return _FakeSettingsRow(dict(self._current))

    def reset_to_defaults(self) -> _FakeSettingsRow:
        self._current = dict(_DEFAULT_SETTINGS)
        return _FakeSettingsRow(dict(self._current))


@pytest.fixture()
def settings_sync_client():
    """A settings-router client wired with a live enhancement_settings dict
    and a mock connection manager, so the sync half can be asserted on."""
    repo = _FakeSettingsRepo()
    enhancement_settings = {"enabled": False, "preset": "adaptive", "intensity": 1.0}
    connection_manager = Mock()
    connection_manager.broadcast = AsyncMock()

    app = FastAPI()
    app.include_router(create_settings_router(
        get_settings_repo=lambda: repo,
        get_enhancement_settings=lambda: enhancement_settings,
        connection_manager=connection_manager,
    ))
    tc = TestClient(app)
    tc._repo = repo  # type: ignore[attr-defined]
    tc._enhancement_settings = enhancement_settings  # type: ignore[attr-defined]
    tc._connection_manager = connection_manager  # type: ignore[attr-defined]
    return tc


class TestSettingsPutSyncsRuntimeDict:
    def test_preset_change_reaches_the_live_session_without_restart(self, settings_sync_client):
        """The exact scenario in the issue: Default Preset -> "warm" must
        affect playback in THIS session, not just the next backend start."""
        resp = settings_sync_client.put("/api/settings", json={"default_preset": "warm"})

        assert resp.status_code == 200
        assert settings_sync_client._enhancement_settings["preset"] == "warm"

    def test_intensity_and_auto_enhance_also_sync(self, settings_sync_client):
        resp = settings_sync_client.put(
            "/api/settings",
            json={"enhancement_intensity": 0.5, "auto_enhance": True},
        )

        assert resp.status_code == 200
        assert settings_sync_client._enhancement_settings["intensity"] == 0.5
        assert settings_sync_client._enhancement_settings["enabled"] is True

    def test_enhancement_change_broadcasts_to_live_clients(self, settings_sync_client):
        settings_sync_client.put("/api/settings", json={"default_preset": "bright"})

        settings_sync_client._connection_manager.broadcast.assert_awaited_once()
        message = settings_sync_client._connection_manager.broadcast.await_args.args[0]
        assert message["type"] == "enhancement_settings_changed"
        assert message["data"]["preset"] == "bright"

    def test_unrelated_field_does_not_touch_enhancement_settings_or_broadcast(
        self, settings_sync_client
    ):
        """A theme/volume-only save has no reason to re-seed or notify
        enhancement consumers — asserts the guard, not just the absence of
        a crash."""
        before = dict(settings_sync_client._enhancement_settings)

        resp = settings_sync_client.put("/api/settings", json={"theme": "light"})

        assert resp.status_code == 200
        assert settings_sync_client._enhancement_settings == before
        settings_sync_client._connection_manager.broadcast.assert_not_awaited()

    def test_reset_always_resyncs_even_though_it_takes_no_payload(self, settings_sync_client):
        """reset_to_defaults() has no `updates` dict to key a guard on — the
        re-seed must fire unconditionally, not only when some tracked field
        set happens to be present."""
        settings_sync_client._enhancement_settings["preset"] = "punchy"
        settings_sync_client._enhancement_settings["intensity"] = 0.2
        settings_sync_client._enhancement_settings["enabled"] = True

        resp = settings_sync_client.post("/api/settings/reset")

        assert resp.status_code == 200
        # reset_to_defaults() -> UserSettings() column defaults, per _FakeSettingsRow.
        assert settings_sync_client._enhancement_settings["preset"] == "adaptive"
        assert settings_sync_client._enhancement_settings["intensity"] == 1.0
        assert settings_sync_client._enhancement_settings["enabled"] is False
        settings_sync_client._connection_manager.broadcast.assert_awaited_once()

    def test_works_with_no_enhancement_wiring_given(self):
        """Backward compatibility: omitting get_enhancement_settings/
        connection_manager (the pre-#4587 call shape) must not raise."""
        repo = _FakeSettingsRepo()
        app = FastAPI()
        app.include_router(create_settings_router(get_settings_repo=lambda: repo))
        tc = TestClient(app)

        resp = tc.put("/api/settings", json={"default_preset": "warm"})

        assert resp.status_code == 200

    def test_broadcast_failure_does_not_fail_the_request(self, settings_sync_client):
        """Mirrors _notify_scanner()'s tolerance: a WS hiccup must not turn a
        successful DB write into a 500."""
        settings_sync_client._connection_manager.broadcast.side_effect = RuntimeError("boom")

        resp = settings_sync_client.put("/api/settings", json={"default_preset": "gentle"})

        assert resp.status_code == 200
        assert settings_sync_client._enhancement_settings["preset"] == "gentle"


# ============================================================================
# Direction 2: enhancement endpoints -> persisted UserSettings
# ============================================================================


class _FakeRepositoryFactory:
    """Records every write so tests can assert what (and how often) reached
    the DB — the same records-what-reached-it pattern as _FakeSettingsRepo."""

    def __init__(self) -> None:
        self.settings = Mock()
        self.settings.update_settings = Mock()


def _build_enhancement_client(enhancement_settings: dict, repos=None) -> TestClient:
    connection_manager = Mock()
    connection_manager.broadcast = AsyncMock()
    router = create_enhancement_router(
        get_enhancement_settings=lambda: enhancement_settings,
        connection_manager=connection_manager,
        get_repository_factory=(lambda: repos) if repos is not None else None,
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestEnhancementEndpointsPersist:
    def test_preset_change_persists_to_settings_repository(self):
        settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
        repos = _FakeRepositoryFactory()
        client = _build_enhancement_client(settings, repos)

        resp = client.post("/api/player/enhancement/preset", json={"preset": "warm"})

        assert resp.status_code == 200
        repos.settings.update_settings.assert_called_once_with({"default_preset": "warm"})

    def test_intensity_change_persists_to_settings_repository(self):
        settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
        repos = _FakeRepositoryFactory()
        client = _build_enhancement_client(settings, repos)

        resp = client.post("/api/player/enhancement/intensity", json={"intensity": 0.6})

        assert resp.status_code == 200
        repos.settings.update_settings.assert_called_once_with({"enhancement_intensity": 0.6})

    def test_toggle_persists_to_settings_repository(self):
        settings = {"enabled": False, "preset": "adaptive", "intensity": 1.0}
        repos = _FakeRepositoryFactory()
        client = _build_enhancement_client(settings, repos)

        resp = client.post("/api/player/enhancement/toggle", json={"enabled": True})

        assert resp.status_code == 200
        repos.settings.update_settings.assert_called_once_with({"auto_enhance": True})

    def test_unchanged_preset_does_not_trigger_a_redundant_write(self):
        """Matches the pre-warm guard's own "avoid redundant work when a
        client re-POSTs the same value" principle (#4425's fix note) —
        applied here to persistence instead of pre-warming."""
        settings = {"enabled": True, "preset": "warm", "intensity": 1.0}
        repos = _FakeRepositoryFactory()
        client = _build_enhancement_client(settings, repos)

        resp = client.post("/api/player/enhancement/preset", json={"preset": "warm"})

        assert resp.status_code == 200
        repos.settings.update_settings.assert_not_called()

    def test_persist_failure_does_not_fail_the_request(self):
        """The runtime change (this endpoint's primary effect) must survive
        a DB hiccup — mirrors settings.py's own broadcast-failure tolerance."""
        settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
        repos = _FakeRepositoryFactory()
        repos.settings.update_settings.side_effect = RuntimeError("db is down")
        client = _build_enhancement_client(settings, repos)

        resp = client.post("/api/player/enhancement/preset", json={"preset": "bright"})

        assert resp.status_code == 200
        assert settings["preset"] == "bright"

    def test_no_repository_factory_given_skips_persistence_without_error(self):
        """Backward compatibility: the pre-#4587 call shape (no
        get_repository_factory) must keep working exactly as before."""
        settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
        client = _build_enhancement_client(settings, repos=None)

        resp = client.post("/api/player/enhancement/preset", json={"preset": "punchy"})

        assert resp.status_code == 200
        assert settings["preset"] == "punchy"


# ============================================================================
# End-to-end: a value written by direction 2 survives a fresh startup seed —
# proves the round trip, not just each direction in isolation.
# ============================================================================


class TestRoundTrip:
    def test_preset_set_via_enhancement_endpoint_survives_a_fresh_seed(self):
        """POST /api/player/enhancement/preset "bright", then run
        seed_enhancement_settings() against the persisted row exactly as
        config/startup.py does on the next process start, and assert the
        value written by direction 2 is what direction-1's seed reads back —
        the acceptance criterion from the issue's Test Plan."""
        from helpers import seed_enhancement_settings

        repo = _FakeSettingsRepo()

        class _FactoryOverDbRepo:
            def __init__(self, settings_repo):
                self.settings = settings_repo

        repos = _FactoryOverDbRepo(repo)
        settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
        client = _build_enhancement_client(settings, repos)

        resp = client.post("/api/player/enhancement/preset", json={"preset": "bright"})
        assert resp.status_code == 200

        # Simulate the next backend startup's one-time seed.
        fresh_runtime_dict = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
        seed_enhancement_settings(fresh_runtime_dict, repo.get_settings())

        assert fresh_runtime_dict["preset"] == "bright"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
