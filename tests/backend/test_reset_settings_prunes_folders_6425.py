"""POST /api/settings/reset prunes tracks under every scan folder it wipes (#6425).

#5467 (remove-folder) and #5523 (PUT diff) made each scan_folders writer
revoke path trust AND prune the folder's tracks through one shared
_revoke_folder step. reset_settings replaced the row (empty scan_folders) and
cleared runtime trust but never pruned, leaving browsable tracks that every
path-validated route rejected with 400.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.settings import create_settings_router
from security.path_allowlist import _extra_allowed_dirs, register_allowed_directory
from tests.backend.test_scan_start_and_cancel_frames import _CapturingManager


def _client(previous_folders, remove_tracks_under_folder, get_library_database=True):
    settings = Mock()
    settings.to_dict.return_value = {'theme': 'auto', 'scan_folders': []}
    repo = Mock()
    repo.reset_to_defaults_with_previous_folders.return_value = (settings, previous_folders)
    manager = _CapturingManager()
    library_database = Mock()
    library_database.tracks.remove_tracks_under_folder = remove_tracks_under_folder

    app = FastAPI()
    app.include_router(create_settings_router(
        get_settings_repo=lambda: repo,
        connection_manager=manager,
        get_library_database=(lambda: library_database) if get_library_database else None,
    ))
    return TestClient(app, raise_server_exceptions=False), manager


def test_reset_prunes_every_previous_scan_folder(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    for folder in (first, second):
        folder.mkdir()
        register_allowed_directory(folder)
    remove_tracks_under_folder = Mock(side_effect=[3, 4])
    try:
        client, manager = _client([str(first), str(second)], remove_tracks_under_folder)

        response = client.post("/api/settings/reset")

        assert response.status_code == 200
        # The reset leaves no scan folders, so nothing is kept.
        assert [c.args for c in remove_tracks_under_folder.call_args_list] == [
            (str(first),), (str(second),),
        ]
        assert all(c.kwargs == {"keep_folders": ()} for c in remove_tracks_under_folder.call_args_list)
        assert [f["type"] for f in manager.frames].count("library_tracks_removed") == 2
        assert first.resolve() not in _extra_allowed_dirs
        assert second.resolve() not in _extra_allowed_dirs
    finally:
        for folder in (first, second):
            if folder.resolve() in _extra_allowed_dirs:
                _extra_allowed_dirs.remove(folder.resolve())


def test_reset_without_previous_folders_never_prunes():
    remove_tracks_under_folder = Mock(return_value=99)
    client, manager = _client([], remove_tracks_under_folder)

    response = client.post("/api/settings/reset")

    assert response.status_code == 200
    remove_tracks_under_folder.assert_not_called()
    assert manager.frames == []


def test_reset_without_library_db_still_succeeds(tmp_path):
    client, manager = _client([str(tmp_path)], Mock(return_value=1), get_library_database=False)

    response = client.post("/api/settings/reset")

    assert response.status_code == 200
    assert manager.frames == []


def test_repository_returns_the_folders_stored_before_the_reset(settings_repository):
    settings_repository.update_settings({"scan_folders": ["/mnt/x", "/mnt/y"]})

    settings, previous = settings_repository.reset_to_defaults_with_previous_folders()

    assert previous == ["/mnt/x", "/mnt/y"]
    assert settings.to_dict()["scan_folders"] == []
    assert settings_repository.reset_to_defaults_with_previous_folders()[1] == []
