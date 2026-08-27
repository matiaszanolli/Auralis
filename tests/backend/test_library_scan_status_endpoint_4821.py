"""Regression tests for GET /api/library/scan/status (#4821).

Library scan lifecycle (library_scan_started/scan_progress/scan_complete/
library_scan_error) is broadcast-only. A client whose WebSocket drops mid-scan
and reconnects after the terminal frame was sent never learns the scan ended,
so `isScanning` gets stuck. This endpoint is a live resync point: it reads the
same scan-slot counter try_acquire_scan_slot()/release_scan_slot() maintain,
so it reflects reality even if a scan crashed without ever broadcasting a
terminal frame.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.library_scan import create_library_scan_router  # noqa: E402


class _FakeLibraryDatabase:
    def __init__(self, scanning: bool) -> None:
        self._scanning = scanning

    def is_scanning(self) -> bool:
        return self._scanning


def _make_app(get_library_database) -> TestClient:
    app = FastAPI()
    router = create_library_scan_router(get_library_database=get_library_database)
    app.include_router(router)
    return TestClient(app)


def test_reports_not_scanning_when_no_scan_active():
    client = _make_app(lambda: _FakeLibraryDatabase(scanning=False))
    response = client.get("/api/library/scan/status")
    assert response.status_code == 200
    assert response.json() == {"is_scanning": False}


def test_reports_scanning_when_a_scan_is_active():
    client = _make_app(lambda: _FakeLibraryDatabase(scanning=True))
    response = client.get("/api/library/scan/status")
    assert response.status_code == 200
    assert response.json() == {"is_scanning": True}


def test_503_when_library_database_unavailable():
    client = _make_app(lambda: None)
    response = client.get("/api/library/scan/status")
    assert response.status_code == 503


def test_503_when_no_getter_configured():
    client = _make_app(None)
    response = client.get("/api/library/scan/status")
    assert response.status_code == 503


def test_reflects_a_crashed_scan_that_never_broadcast_a_terminal_frame():
    """The core self-healing property: this is a live read of the scan-slot
    counter, not a cached/replayed broadcast frame, so it can't go stale from
    a missed WebSocket send."""
    manager = _FakeLibraryDatabase(scanning=True)
    client = _make_app(lambda: manager)

    assert client.get("/api/library/scan/status").json() == {"is_scanning": True}

    # Scanner crashes; its `finally` block releases the slot without ever
    # broadcasting scan_complete/library_scan_error.
    manager._scanning = False

    assert client.get("/api/library/scan/status").json() == {"is_scanning": False}
