"""
POST /api/settings/scan-folders/delete prunes tracks under the removed
folder (#5467).

Removing a scan folder revoked path trust for its files
(unregister_allowed_directory) but never touched the Track rows pointing
into it -- they stayed visible in the library while every path-validated
endpoint (metadata, tracks, enhancement) started rejecting them with an
unexplained 400. Wired directly against create_settings_router (not the
full main.py app) for full control over connection_manager and
get_library_database, matching the pattern in
test_manual_scan_prunes_missing_5458.py.
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
from tests.backend.test_scan_start_and_cancel_frames import _CapturingManager


def _mock_settings():
    settings = Mock()
    settings.to_dict.return_value = {'theme': 'dark', 'scan_folders': [], 'auto_scan': True}
    return settings


def _client(remove_tracks_under_folder, get_library_database=True):
    settings_repo = Mock()
    settings_repo.remove_scan_folder.return_value = _mock_settings()

    library_database = Mock()
    library_database.tracks.remove_tracks_under_folder = remove_tracks_under_folder

    manager = _CapturingManager()

    app = FastAPI()
    app.include_router(create_settings_router(
        get_settings_repo=lambda: settings_repo,
        connection_manager=manager,
        get_library_database=(lambda: library_database) if get_library_database else None,
    ))
    return TestClient(app, raise_server_exceptions=False), manager


def _with_registered_dir(tmp_path, fn):
    """Register+unregister a real removed_dir around `fn(removed_dir)`,
    matching test_main_api.py's TestSettingsEndpoints cleanup pattern so
    this test doesn't leak global allowlist state into others."""
    from security.path_security import _extra_allowed_dirs, register_allowed_directory

    removed_dir = tmp_path / "removed"
    removed_dir.mkdir()
    register_allowed_directory(removed_dir)
    try:
        fn(removed_dir)
    finally:
        if removed_dir.resolve() in _extra_allowed_dirs:
            _extra_allowed_dirs.remove(removed_dir.resolve())


def test_removes_tracks_under_the_removed_folder(tmp_path):
    remove_tracks_under_folder = Mock(return_value=4)
    client, manager = _client(remove_tracks_under_folder)

    def _run(removed_dir):
        response = client.post(
            "/api/settings/scan-folders/delete", json={"folder": str(removed_dir)}
        )
        assert response.status_code == 200
        remove_tracks_under_folder.assert_called_once_with(str(removed_dir))
        assert manager.frames == [{"type": "library_tracks_removed", "data": {"count": 4}}]

    _with_registered_dir(tmp_path, _run)


def test_no_broadcast_when_no_tracks_under_the_folder(tmp_path):
    remove_tracks_under_folder = Mock(return_value=0)
    client, manager = _client(remove_tracks_under_folder)

    def _run(removed_dir):
        response = client.post(
            "/api/settings/scan-folders/delete", json={"folder": str(removed_dir)}
        )
        assert response.status_code == 200
        assert manager.frames == []

    _with_registered_dir(tmp_path, _run)


def test_no_library_database_is_a_no_op_not_a_crash(tmp_path):
    """When get_library_database is not wired (e.g. Auralis components never
    finished initializing), the folder is still removed from settings and
    unregistered -- pruning is best-effort, not required for success."""
    client, manager = _client(Mock(), get_library_database=False)

    def _run(removed_dir):
        response = client.post(
            "/api/settings/scan-folders/delete", json={"folder": str(removed_dir)}
        )
        assert response.status_code == 200
        assert manager.frames == []

    _with_registered_dir(tmp_path, _run)
