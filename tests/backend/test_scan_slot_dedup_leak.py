"""Regression test for the scan-slot leak on dedup rejection (#4330).

Scanner.scan_directories() acquires a concurrency scan slot, then hits the
per-directory dedup guard. When that guard rejects a scan (the directory is
already being scanned), the old code `return`ed BEFORE the try/finally that
releases the slot — leaking one slot permanently. After max_concurrent_scans
such rejections, _active_scans saturates and ALL subsequent scans are rejected
at the slot guard until process restart.

The fix releases the slot in the dedup-reject branch (without falling through
the finally, which would also strip the OTHER scan's paths from the shared
dedup set).

#4509: the dedup set itself moved from LibraryScanner (`._active_paths`, an
instance attribute reset to empty on every fresh scanner) onto library_manager
(`try_reserve_scan_paths`/`release_scan_paths`) — every real caller constructs
a new LibraryScanner per scan, so the guard has to live on the one object
those calls actually share. This test's mock now backs those two methods with
a real shared set instead of manipulating `scanner._active_paths` directly.
"""

import os
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.scanner.scanner import LibraryScanner


def _make_scanner_with_slot_counter(max_scans: int = 2):
    """Return (scanner, state) where state['active'] tracks live scan slots
    and state['paths'] tracks reserved dedup paths, using the real
    acquire/release semantics of LibraryDatabase."""
    state = {"active": 0, "max": max_scans, "paths": set()}
    lock = threading.Lock()

    def _acquire():
        with lock:
            if state["active"] >= state["max"]:
                return (False, state["max"])
            state["active"] += 1
            return (True, state["max"])

    def _release():
        with lock:
            state["active"] = max(0, state["active"] - 1)

    def _reserve_paths(paths):
        with lock:
            clashing = [p for p in paths if p in state["paths"]]
            if clashing:
                return clashing
            state["paths"].update(paths)
            return []

    def _release_paths(paths):
        with lock:
            state["paths"].difference_update(paths)

    lm = MagicMock()
    lm.try_acquire_scan_slot.side_effect = _acquire
    lm.release_scan_slot.side_effect = _release
    lm.try_reserve_scan_paths.side_effect = _reserve_paths
    lm.release_scan_paths.side_effect = _release_paths

    return LibraryScanner(lm), state


def test_dedup_rejection_releases_scan_slot(tmp_path):
    scanner, state = _make_scanner_with_slot_counter(max_scans=2)

    busy = str(tmp_path / "busy")
    os.makedirs(busy, exist_ok=True)
    normalized = os.path.normpath(os.path.abspath(busy))

    # Simulate another scan already owning this directory.
    state["paths"].add(normalized)

    # Reject more times than there are slots — with the leak, the third would
    # already be starved because the slot counter would be pinned at max.
    for i in range(state["max"] + 1):
        result = scanner.scan_directories([busy])
        assert result.rejected, f"iteration {i}: expected a dedup rejection"
        assert state["active"] == 0, (
            f"iteration {i}: scan slot leaked on dedup rejection "
            f"(active={state['active']}) — regression of #4330"
        )

    # The dedup-reject branch must NOT have released the other scan's path
    # (it never reserved it in the first place on this path).
    assert normalized in state["paths"], (
        "dedup-reject path released the OTHER scan's reserved path"
    )

    # Acceptance criterion: a fresh, non-overlapping scan can still acquire.
    acquired, _ = scanner.library_manager.try_acquire_scan_slot()
    assert acquired, "a fresh scan was starved — the slot pool never recovered"
