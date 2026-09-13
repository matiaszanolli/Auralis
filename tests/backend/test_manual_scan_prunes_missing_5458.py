"""A manual library scan prunes tracks whose files are gone (#5458).

Only the auto-scanner called cleanup_missing_files(), so POST /api/library/scan
(the "Scan Folder" and "Scan Now" buttons) never pruned: users with auto_scan
off kept dead entries forever. Both paths now share prune_missing_tracks().
"""

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# tests/backend/conftest.py puts auralis-web/backend on sys.path.
from routers import library_scan
from routers.library_scan import create_library_scan_router
from services import library_auto_scanner
from services.missing_tracks import prune_missing_tracks
from tests.backend.test_scan_start_and_cancel_frames import (
    _AcceptingScanner,
    _CapturingManager,
    _RejectingScanner,
)


def _client(scanner_cls, monkeypatch, cleanup):
    import auralis.library.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "LibraryScanner", scanner_cls)
    library_database = SimpleNamespace(tracks=SimpleNamespace(cleanup_missing_files=cleanup))
    manager = _CapturingManager()
    app = FastAPI()
    app.include_router(
        create_library_scan_router(lambda: library_database, connection_manager=manager)
    )
    return TestClient(app, raise_server_exceptions=False), manager


def test_manual_scan_prunes_and_announces_before_scan_complete(monkeypatch, tmp_path):
    cleanup = Mock(return_value=2)
    client, manager = _client(_AcceptingScanner, monkeypatch, cleanup)

    response = client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    assert response.status_code == 200
    cleanup.assert_called_once_with()
    removed = [f for f in manager.frames if f["type"] == "library_tracks_removed"]
    assert [f["data"] for f in removed] == [{"count": 2}]
    types = manager.types()
    assert types.index("library_tracks_removed") < types.index("scan_complete"), (
        "useScanProgress counts a removal only while the scan is in progress"
    )


def test_nothing_removed_sends_no_removal_frame(monkeypatch, tmp_path):
    client, manager = _client(_AcceptingScanner, monkeypatch, Mock(return_value=0))

    client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    assert "library_tracks_removed" not in manager.types()
    assert "scan_complete" in manager.types()


def test_rejected_scan_does_not_prune(monkeypatch, tmp_path):
    cleanup = Mock(return_value=5)
    client, _manager = _client(_RejectingScanner, monkeypatch, cleanup)

    response = client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    assert response.status_code == 409
    cleanup.assert_not_called()


def test_a_failing_prune_does_not_fail_the_scan(monkeypatch, tmp_path):
    client, manager = _client(
        _AcceptingScanner, monkeypatch, Mock(side_effect=OSError("disk gone"))
    )

    response = client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    assert response.status_code == 200
    assert "scan_complete" in manager.types()
    assert "library_tracks_removed" not in manager.types()


@pytest.mark.asyncio
async def test_prune_without_a_connection_manager_still_prunes():
    library_database = SimpleNamespace(
        tracks=SimpleNamespace(cleanup_missing_files=Mock(return_value=3))
    )

    assert await prune_missing_tracks(library_database, None) == 3


@pytest.mark.asyncio
async def test_prune_broadcasts_the_auto_scanner_payload_shape():
    manager = Mock()
    manager.broadcast = AsyncMock()
    library_database = SimpleNamespace(
        tracks=SimpleNamespace(cleanup_missing_files=Mock(return_value=4))
    )

    await prune_missing_tracks(library_database, manager)

    manager.broadcast.assert_awaited_once()
    frame = manager.broadcast.await_args.args[0]
    assert frame["type"] == "library_tracks_removed"
    assert frame["data"] == {"count": 4}


def test_both_scan_paths_prune_through_the_shared_helper():
    """WIRING: neither path keeps its own copy of the prune logic."""
    for module in (library_scan, library_auto_scanner):
        source = inspect.getsource(module)
        assert "prune_missing_tracks(" in source, module.__name__
        assert "cleanup_missing_files" not in source, module.__name__
