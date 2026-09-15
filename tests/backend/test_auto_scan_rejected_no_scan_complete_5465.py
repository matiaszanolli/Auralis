"""A rejected auto-scan cycle must not broadcast scan_complete (#5465).

`_do_scan` broadcast an all-zero `scan_complete` unconditionally, even when
`scan_result.rejected` was True (the auto-scan cycle lost the scan-slot race
to a concurrent manual scan). `useScanProgress.ts` resets to its initial
state on every `scan_complete` frame, so a manual scan actually still
running lost its progress bar and briefly showed "+0 added (0.0s)".

The manual router (routers/library_scan.py) already guards on
`result.rejected` (raises 409 before building any scan_complete), and
scanner.py:424 already guards its on_scan_complete callback the same way
-- the auto-scanner's completion broadcast was the one remaining
unguarded site.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from services.library_auto_scanner import LibraryAutoScanner
from tests.backend.test_scan_start_and_cancel_frames import (
    _AcceptingScanner,
    _CapturingManager,
    _RejectingScanner,
)


def _make_scanner(scanner_cls, monkeypatch):
    import auralis.library.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "LibraryScanner", scanner_cls)

    settings_repo = MagicMock()
    library_database = MagicMock()
    manager = _CapturingManager()
    scanner = LibraryAutoScanner(
        settings_repo=settings_repo,
        library_database=library_database,
        fingerprint_queue=None,
        connection_manager=manager,
    )
    return scanner, manager


@pytest.mark.asyncio
async def test_rejected_cycle_broadcasts_no_scan_complete(monkeypatch):
    scanner, manager = _make_scanner(_RejectingScanner, monkeypatch)

    await scanner._do_scan(["/music"])

    assert "scan_complete" not in manager.types(), (
        "a rejected auto-scan cycle must not reset the UI of the scan that "
        "actually owns the slot"
    )


@pytest.mark.asyncio
async def test_rejected_cycle_does_not_prune_missing_tracks(monkeypatch):
    import services.library_auto_scanner as auto_scanner_mod

    scanner, _manager = _make_scanner(_RejectingScanner, monkeypatch)
    prune = AsyncMock(return_value=0)
    monkeypatch.setattr(auto_scanner_mod, "prune_missing_tracks", prune)

    await scanner._do_scan(["/music"])

    prune.assert_not_called()


@pytest.mark.asyncio
async def test_rejected_cycle_does_not_enqueue_fingerprints(monkeypatch):
    scanner, _manager = _make_scanner(_RejectingScanner, monkeypatch)
    scanner._fingerprint_queue = MagicMock()  # would be truthy if reached

    with patch(
        "analysis.fingerprint_queue.get_fingerprint_queue",
        side_effect=AssertionError("must not be called for a rejected scan"),
    ):
        await scanner._do_scan(["/music"])


@pytest.mark.asyncio
async def test_accepted_cycle_still_broadcasts_scan_complete(monkeypatch):
    """Sanity check: the guard doesn't suppress the normal, accepted path."""
    import services.library_auto_scanner as auto_scanner_mod

    scanner, manager = _make_scanner(_AcceptingScanner, monkeypatch)
    monkeypatch.setattr(auto_scanner_mod, "prune_missing_tracks", AsyncMock(return_value=0))

    await scanner._do_scan(["/music"])

    assert "scan_complete" in manager.types()
