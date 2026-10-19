"""PUT /api/settings prunes tracks under scan folders removed in the diff (#5523).

#5467 gave the dedicated POST /api/settings/scan-folders/delete endpoint the
revoke-trust + prune-tracks treatment. The generic PUT accepts a full
replacement ``scan_folders`` array and revokes trust for every dropped entry,
but skipped the prune — Track rows under the folder stayed visible/browsable
while every path-validated endpoint began rejecting their files with an
unexplained 400. Both routes now go through one shared _revoke_folder helper
so they cannot drift again.
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
from security.path_security import _extra_allowed_dirs, register_allowed_directory
from tests.backend.test_scan_start_and_cancel_frames import _CapturingManager


def _settings_repo(previous_folders):
    settings = Mock()
    settings.to_dict.return_value = {'theme': 'dark', 'scan_folders': [], 'auto_scan': True}
    repo = Mock()
    repo.update_settings_with_previous_folders.return_value = (settings, previous_folders)
    return repo


def _client(previous_folders, remove_tracks_under_folder, get_library_database=True):
    manager = _CapturingManager()
    library_database = Mock()
    library_database.tracks.remove_tracks_under_folder = remove_tracks_under_folder

    app = FastAPI()
    app.include_router(create_settings_router(
        get_settings_repo=lambda: _settings_repo(previous_folders),
        connection_manager=manager,
        get_library_database=(lambda: library_database) if get_library_database else None,
    ))
    return TestClient(app, raise_server_exceptions=False), manager


def _with_registered_dir(tmp_path, fn):
    """Register+clean up a real removed_dir around `fn(removed_dir)`, matching
    test_remove_scan_folder_prunes_tracks_5467.py so this test doesn't leak
    global allowlist state into others."""
    removed_dir = tmp_path / "removed-via-put"
    removed_dir.mkdir()
    register_allowed_directory(removed_dir)
    try:
        fn(removed_dir)
    finally:
        if removed_dir.resolve() in _extra_allowed_dirs:
            _extra_allowed_dirs.remove(removed_dir.resolve())


def test_put_dropping_a_folder_prunes_its_tracks(tmp_path):
    remove_tracks_under_folder = Mock(return_value=6)
    kept = tmp_path  # must exist: the PUT payload runs validate_directory_list

    def _run(removed_dir):
        client, manager = _client(
            [str(kept), str(removed_dir)], remove_tracks_under_folder
        )

        response = client.put(
            "/api/settings", json={"scan_folders": [str(kept)]}
        )

        assert response.status_code == 200
        remove_tracks_under_folder.assert_called_once_with(str(removed_dir))
        assert manager.frames == [
            {"type": "library_tracks_removed", "data": {"count": 6}},
            {"type": "library_updated", "data": {"action": "update", "track_count": 0}},
        ]
        # Trust is revoked as before (#3842) — the prune is on top of it.
        assert removed_dir.resolve() not in _extra_allowed_dirs

    _with_registered_dir(tmp_path, _run)


def test_put_without_scan_folders_never_prunes(tmp_path):
    remove_tracks_under_folder = Mock(return_value=99)
    client, manager = _client([], remove_tracks_under_folder)

    response = client.put("/api/settings", json={"theme": "dark"})

    assert response.status_code == 200
    remove_tracks_under_folder.assert_not_called()
    assert manager.frames == []


def test_put_folder_removal_without_library_db_still_succeeds(tmp_path):
    """No LibraryDatabase wired: trust is still revoked, nothing prunes, and
    the PUT succeeds — same best-effort contract as the dedicated endpoint."""
    kept = tmp_path

    def _run(removed_dir):
        client, manager = _client(
            [str(kept), str(removed_dir)], Mock(return_value=1),
            get_library_database=False,
        )

        response = client.put("/api/settings", json={"scan_folders": [str(kept)]})

        assert response.status_code == 200
        assert manager.frames == []

    _with_registered_dir(tmp_path, _run)
