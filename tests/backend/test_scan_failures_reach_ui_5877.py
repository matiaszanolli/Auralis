"""Both scan emitters surface a failed or incomplete scan (#5877).

An aborted scan was reported as a normal ``scan_complete`` ("+0 added"), and
unreadable folders never reached the UI. An incomplete walk must also not
prune: a configured folder on an unplugged drive looks like every one of its
tracks went missing.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from auralis.library.scan_models import ScanResult  # noqa: E402
from routers.library_scan import create_library_scan_router  # noqa: E402
from services.library_auto_scanner import LibraryAutoScanner  # noqa: E402
from tests.backend.test_scan_start_and_cancel_frames import _BaseScanner, _CapturingManager  # noqa: E402


def _aborted() -> ScanResult:
    return ScanResult(error="RuntimeError during library scan")


def _unreadable_folder() -> ScanResult:
    result = ScanResult(files_found=3, files_processed=3, files_added=3, directories_scanned=1)
    result.record_directory_error("/music/Locked Album", "permission denied")
    return result


def _scanner_returning(make_result):
    class _Scanner(_BaseScanner):
        def scan_directories(self, directories=(), **_kwargs):
            return make_result()
    return _Scanner


def _manual(monkeypatch, make_result):
    import auralis.library.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "LibraryScanner", _scanner_returning(make_result))
    cleanup = Mock(return_value=5)
    library_database = SimpleNamespace(tracks=SimpleNamespace(cleanup_missing_files=cleanup))
    manager = _CapturingManager()
    app = FastAPI()
    app.include_router(create_library_scan_router(lambda: library_database, connection_manager=manager))
    return TestClient(app, raise_server_exceptions=False), manager, cleanup


def test_manual_aborted_scan_is_an_error_not_a_completion(monkeypatch, tmp_path):
    client, manager, cleanup = _manual(monkeypatch, _aborted)

    response = client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    assert response.status_code == 500
    assert "scan_complete" not in manager.types()
    [error] = [f for f in manager.frames if f["type"] == "library_scan_error"]
    assert error["data"] == {"error": "RuntimeError during library scan"}
    cleanup.assert_not_called()


def test_manual_unreadable_folder_is_reported_and_blocks_pruning(monkeypatch, tmp_path):
    client, manager, cleanup = _manual(monkeypatch, _unreadable_folder)

    response = client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    assert response.status_code == 200
    named = [{"filename": "Locked Album", "reason": "permission denied"}]
    assert response.json()["directory_errors"] == named
    [complete] = [f for f in manager.frames if f["type"] == "scan_complete"]
    assert complete["data"]["directory_errors"] == named
    cleanup.assert_not_called()


def _auto(monkeypatch, make_result):
    import auralis.library.scanner as scanner_mod
    import services.library_auto_scanner as auto_scanner_mod

    monkeypatch.setattr(scanner_mod, "LibraryScanner", _scanner_returning(make_result))
    prune = AsyncMock(return_value=5)
    monkeypatch.setattr(auto_scanner_mod, "prune_missing_tracks", prune)
    manager = _CapturingManager()
    scanner = LibraryAutoScanner(
        settings_repo=MagicMock(), library_database=MagicMock(),
        fingerprint_queue=None, connection_manager=manager,
    )
    return scanner, manager, prune


@pytest.mark.asyncio
async def test_auto_aborted_scan_is_an_error_not_a_completion(monkeypatch):
    scanner, manager, prune = _auto(monkeypatch, _aborted)

    await scanner._do_scan(["/music"])

    assert manager.types() == ["library_scan_error"]
    prune.assert_not_called()


@pytest.mark.asyncio
async def test_auto_unreadable_folder_is_reported_and_blocks_pruning(monkeypatch):
    scanner, manager, prune = _auto(monkeypatch, _unreadable_folder)

    await scanner._do_scan(["/music"])

    [complete] = [f for f in manager.frames if f["type"] == "scan_complete"]
    assert complete["data"]["directory_errors"] == [{"filename": "Locked Album", "reason": "permission denied"}]
    prune.assert_not_called()


@pytest.mark.asyncio
async def test_auto_complete_walk_still_prunes(monkeypatch):
    scanner, _manager, prune = _auto(monkeypatch, lambda: ScanResult(files_found=1, directories_scanned=1))

    await scanner._do_scan(["/music"])

    prune.assert_awaited_once()
