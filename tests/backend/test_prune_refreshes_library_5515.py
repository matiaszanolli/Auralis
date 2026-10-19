"""Prune-only removals refresh the open library view (#5515).

useLibraryWithStats refetches on ``library_updated`` — the only refetch
trigger in the app. Two removal paths never fired it:

- POST /api/library/scan discarded prune_missing_tracks' return value, and
  its library_updated guard had no ``removed`` term — so a rescan that only
  cleaned up files deleted on disk left the view stale.
- Removing a scan folder (and pruning its tracks) broadcast only
  library_tracks_removed, which useScanProgress consumes purely as the
  scan-result counter.

Both now fold the prune count into a library_updated broadcast, matching
the auto-scanner's ``files_added or removed`` guard.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# tests/backend/conftest.py puts auralis-web/backend on sys.path.
from routers.library_scan import create_library_scan_router
from services.missing_tracks import prune_tracks_under_folder
from tests.backend.test_scan_start_and_cancel_frames import (
    _AcceptingScanner,
    _CapturingManager,
)

import auralis.library.scanner as scanner_mod


class _PruneOnlyScanner(_AcceptingScanner):
    """A scan that adds and updates nothing — only the prune did work."""

    def scan_directories(self, directories=(), **_kwargs):
        self._report({'stage': 'started', 'directories': list(directories)})
        return SimpleNamespace(
            rejected=False, added_tracks=[], files_found=10, files_processed=10,
            files_added=0, files_updated=0, files_skipped=10, files_failed=0,
            scan_time=1.5, directories_scanned=1,
            failures=[],
        )


def _client(scanner_cls, monkeypatch, cleanup):
    monkeypatch.setattr(scanner_mod, "LibraryScanner", scanner_cls)
    library_database = SimpleNamespace(tracks=SimpleNamespace(cleanup_missing_files=cleanup))
    manager = _CapturingManager()
    app = FastAPI()
    app.include_router(
        create_library_scan_router(lambda: library_database, connection_manager=manager)
    )
    return TestClient(app, raise_server_exceptions=False), manager


def test_prune_only_rescan_broadcasts_library_updated(monkeypatch, tmp_path):
    """A rescan that only prunes deleted files still refreshes the view."""
    client, manager = _client(_PruneOnlyScanner, monkeypatch, Mock(return_value=4))

    response = client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    assert response.status_code == 200
    updated = [f for f in manager.frames if f["type"] == "library_updated"]
    assert updated == [{"type": "library_updated",
                        "data": {"action": "scan", "track_count": 0}}]
    types = manager.types()
    assert types.index("library_updated") > types.index("scan_complete"), (
        "the refresh announcement follows the terminal scan frame"
    )


def test_clean_rescan_with_no_changes_stays_silent(monkeypatch, tmp_path):
    """No additions, no updates, no prune — no library_updated."""
    client, manager = _client(_PruneOnlyScanner, monkeypatch, Mock(return_value=0))

    client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    assert "library_updated" not in manager.types()
    assert "scan_complete" in manager.types()


def test_adding_scan_still_reports_the_added_count(monkeypatch, tmp_path):
    """The prune count must not clobber the pre-existing added/updated path."""
    client, manager = _client(_AcceptingScanner, monkeypatch, Mock(return_value=0))

    client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    updated = [f for f in manager.frames if f["type"] == "library_updated"]
    assert updated == [{"type": "library_updated",
                        "data": {"action": "scan", "track_count": 2}}]


@pytest.mark.asyncio
async def test_folder_removal_prune_broadcasts_library_updated():
    """remove_scan_folder's prune announces the refresh (#5515)."""
    library_database = Mock()
    library_database.tracks = SimpleNamespace(
        remove_tracks_under_folder=Mock(return_value=7)
    )
    manager = _CapturingManager()

    removed = await prune_tracks_under_folder(library_database, "/music/gone", manager)

    assert removed == 7
    assert [f["type"] for f in manager.frames] == [
        "library_tracks_removed",
        "library_updated",
    ]
    assert manager.frames[1]["data"] == {"action": "update", "track_count": 0}


@pytest.mark.asyncio
async def test_folder_prune_with_nothing_removed_broadcasts_nothing():
    library_database = Mock()
    library_database.tracks = SimpleNamespace(
        remove_tracks_under_folder=Mock(return_value=0)
    )
    manager = _CapturingManager()

    await prune_tracks_under_folder(library_database, "/music/gone", manager)

    assert manager.frames == []
