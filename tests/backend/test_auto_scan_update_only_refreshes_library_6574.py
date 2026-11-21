"""An auto-scan that only updates rows refreshes the open library views (#6574).

The manual scan route broadcast ``library_updated`` when ``files_added or files_updated or
removed``; the auto-scanner's inline copy tested only ``files_added or removed``. A background
rescan that only UPDATED rows - a retagged or replaced file, or one relocated after a move -
emitted ``scan_complete`` but never ``library_updated``, so open Library/Albums/Artists views kept
showing pre-scan metadata. Both emitters now share ``services.scan_complete_broadcast``.
"""
import inspect
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import services.library_auto_scanner as auto_scanner_mod  # noqa: E402
from routers import library_scan_events  # noqa: E402
from services.library_auto_scanner import LibraryAutoScanner  # noqa: E402
from tests.backend.test_scan_start_and_cancel_frames import _AcceptingScanner, _CapturingManager  # noqa: E402

from auralis.library.scan_models import ScanResult  # noqa: E402


def _scanner_reporting(**counts):
    class _Scanner(_AcceptingScanner):
        def scan_directories(self, directories=(), **_kwargs):
            self._report({'stage': 'started', 'directories': list(directories)})
            return ScanResult(files_found=10, files_processed=10, scan_time=1.0, directories_scanned=1, **counts)

    return _Scanner


async def _run_cycle(monkeypatch, removed: int = 0, **counts):
    import auralis.library.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "LibraryScanner", _scanner_reporting(**counts))
    monkeypatch.setattr(auto_scanner_mod, "prune_missing_tracks", AsyncMock(return_value=removed))
    manager = _CapturingManager()
    scanner = LibraryAutoScanner(
        settings_repo=MagicMock(), library_database=MagicMock(), fingerprint_queue=None, connection_manager=manager,
    )
    await scanner._do_scan(["/music"])
    return manager


@pytest.mark.asyncio
async def test_an_update_only_auto_scan_broadcasts_library_updated(monkeypatch):
    manager = await _run_cycle(monkeypatch, files_updated=2)

    updated = [f for f in manager.frames if f["type"] == "library_updated"]
    assert updated == [{"type": "library_updated", "data": {"action": "scan", "track_count": 0}}]
    types = manager.types()
    assert types.index("library_updated") > types.index("scan_complete")


@pytest.mark.asyncio
async def test_an_auto_scan_that_changed_nothing_stays_silent(monkeypatch):
    manager = await _run_cycle(monkeypatch, files_skipped=10)

    assert "scan_complete" in manager.types()
    assert "library_updated" not in manager.types()


@pytest.mark.asyncio
async def test_prune_only_and_adding_auto_scans_still_refresh(monkeypatch):
    pruned = await _run_cycle(monkeypatch, removed=3)
    added = await _run_cycle(monkeypatch, files_added=4)

    assert [f["data"] for f in pruned.frames if f["type"] == "library_updated"] == [{"action": "scan", "track_count": 0}]
    assert [f["data"] for f in added.frames if f["type"] == "library_updated"] == [{"action": "scan", "track_count": 4}]


def test_both_emitters_publish_through_the_shared_helper():
    """WIRING: neither emitter keeps its own copy of the library_updated decision."""
    for module in (library_scan_events, auto_scanner_mod):
        source = inspect.getsource(module)
        assert "broadcast_scan_complete(" in source, module.__name__
        assert '"library_updated"' not in source, module.__name__
