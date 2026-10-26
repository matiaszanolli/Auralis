"""
POST /api/settings/scan-folders/delete only prunes what was really configured (#5941)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The handler took ``body.folder`` as a bare string and ran revoke+prune
unconditionally, although ``SettingsRepository.remove_scan_folder`` silently
did nothing for a string not in the list. ``{"folder": "/"}`` therefore deleted
every track while the settings stayed unchanged, an equivalent spelling of a
configured folder (trailing slash) failed the membership test, and removing a
parent deleted the tracks of a still-configured nested folder.

These tests use the real settings and track repositories.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.settings import create_settings_router  # noqa: E402
from security.path_allowlist import register_allowed_directory, unregister_allowed_directory  # noqa: E402
from tests.backend.test_scan_start_and_cancel_frames import _CapturingManager  # noqa: E402


def _add_track(track_repository, path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    track_repository.add({
        "title": title, "filepath": str(path), "duration": 30.0,
        "sample_rate": 44100, "channels": 2, "format": "WAV",
    })


def _titles(track_repository) -> list[str]:
    tracks, _ = track_repository.get_all(limit=50, offset=0)
    return sorted(t.title for t in tracks)


def _folders(settings_repository) -> list[str]:
    stored = settings_repository.get_settings().scan_folders
    return json.loads(stored) if stored else []


@pytest.fixture
def library(tmp_path, settings_repository, track_repository):
    """Scan folders music, music/nested and side, a track under each, plus one elsewhere."""
    music = tmp_path / "music"
    nested = music / "nested"
    side = tmp_path / "side"
    for folder in (music, nested, side):
        folder.mkdir(parents=True, exist_ok=True)
        register_allowed_directory(folder)
        settings_repository.add_scan_folder(str(folder.resolve()))
    _add_track(track_repository, music / "top.wav", "top")
    _add_track(track_repository, nested / "deep.wav", "deep")
    _add_track(track_repository, side / "side.wav", "side")
    _add_track(track_repository, tmp_path / "elsewhere" / "other.wav", "other")

    app = FastAPI()
    app.include_router(create_settings_router(
        get_settings_repo=lambda: settings_repository,
        connection_manager=_CapturingManager(),
        get_library_database=lambda: SimpleNamespace(tracks=track_repository),
    ))
    yield SimpleNamespace(
        client=TestClient(app, raise_server_exceptions=False),
        music=music, nested=nested, side=side, root=tmp_path,
    )
    for folder in (music, nested, side):
        unregister_allowed_directory(folder)


def _delete(library, folder: str):
    return library.client.post("/api/settings/scan-folders/delete", json={"folder": folder})


def test_deleting_an_unconfigured_folder_removes_nothing(library, settings_repository, track_repository):
    before = _folders(settings_repository)

    for unconfigured in ("/", str(library.root), "."):
        assert _delete(library, unconfigured).status_code == 200

    assert _titles(track_repository) == ["deep", "other", "side", "top"]
    assert _folders(settings_repository) == before


def test_equivalent_spelling_of_a_configured_folder_is_removed_and_pruned(
    library, settings_repository, track_repository
):
    assert _delete(library, str(library.side) + "/").status_code == 200

    assert str(library.side.resolve()) not in _folders(settings_repository)
    assert _titles(track_repository) == ["deep", "other", "top"]


def test_removing_a_parent_keeps_tracks_of_a_still_configured_nested_folder(
    library, settings_repository, track_repository
):
    assert _delete(library, str(library.music.resolve())).status_code == 200

    assert sorted(_folders(settings_repository)) == sorted(
        [str(library.nested.resolve()), str(library.side.resolve())]
    )
    assert _titles(track_repository) == ["deep", "other", "side"]


def test_embedded_nul_byte_removes_nothing(library, settings_repository, track_repository):
    response = _delete(library, str(library.music) + "\0")

    assert response.status_code == 200
    assert _titles(track_repository) == ["deep", "other", "side", "top"]
    assert len(_folders(settings_repository)) == 3
