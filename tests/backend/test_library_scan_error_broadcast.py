"""Regression tests for manual-scan terminal error broadcast (#4413).

The manual scan endpoint emits `library_scan_started` (frontend sets
isScanning=true) but, on timeout or an unexpected exception, previously raised
504/500 WITHOUT a terminal WS frame. useScanProgress clears isScanning only on
`scan_complete`/`library_scan_error`, so the scan card stayed stuck
"Scanning...". The endpoint now broadcasts `library_scan_error` in both branches
before raising -- mirroring the auto-scanner (class-name-only redaction, #3543).

#4602 moved the start frame: the router no longer broadcasts it on entry, since
at that point a rejected scan is indistinguishable from an accepted one. The
scanner now reports a `stage: 'started'` progress event once it owns the scan
slot, and the router translates that into the frame. The fakes below emulate
that, so these tests still assert the full started → error sequence.
"""

import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.library_scan import create_library_scan_router  # noqa: E402


class _CapturingManager:
    """Async connection manager that records every broadcast frame."""

    def __init__(self) -> None:
        self.frames: list[dict] = []

    async def broadcast(self, message: dict) -> None:
        self.frames.append(message)

    def types(self) -> list[str]:
        return [f.get("type") for f in self.frames]


class _StartReportingScanner:
    """Base fake that emits the real scanner's post-guard `started` event (#4602)."""

    def __init__(self, _manager) -> None:
        self._cb = None

    def set_progress_callback(self, cb) -> None:
        self._cb = cb

    def _report_started(self, directories) -> None:
        if self._cb:
            self._cb({'stage': 'started', 'directories': list(directories)})

    def stop_scan(self) -> None:  # pragma: no cover - overridden where needed
        pass


class _TimeoutScanner(_StartReportingScanner):
    """Blocks until stop_scan(), so asyncio.wait_for hits the scan timeout."""

    def __init__(self, _manager) -> None:
        super().__init__(_manager)
        self._stop = threading.Event()

    def scan_directories(self, directories=(), **_kwargs):
        self._report_started(directories)
        # Return promptly once stop_scan fires so the 5s grace wait completes;
        # the result is discarded because the timeout is re-raised.
        self._stop.wait(timeout=10)
        return SimpleNamespace(rejected=False, added_tracks=[])

    def stop_scan(self) -> None:
        self._stop.set()


class _ExplodingScanner(_StartReportingScanner):
    """Raises immediately to exercise the generic-exception branch."""

    def scan_directories(self, directories=(), **_kwargs):
        self._report_started(directories)
        raise ValueError("/secret/path/that/must/not/leak")


def _client(scanner_cls, monkeypatch) -> tuple[TestClient, _CapturingManager]:
    import auralis.library.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "LibraryScanner", scanner_cls)
    manager = _CapturingManager()
    app = FastAPI()
    app.include_router(
        create_library_scan_router(lambda: SimpleNamespace(), connection_manager=manager)
    )
    return TestClient(app, raise_server_exceptions=False), manager


def test_timeout_broadcasts_scan_error_before_504(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AURALIS_SCAN_TIMEOUT", "0.05")
    client, manager = _client(_TimeoutScanner, monkeypatch)

    resp = client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    assert resp.status_code == 504
    # Started up front, then a terminal error frame so the UI leaves scanning.
    assert manager.types() == ["library_scan_started", "library_scan_error"]
    assert "timed out" in manager.frames[-1]["data"]["error"]


def test_exception_broadcasts_scan_error_before_500(monkeypatch, tmp_path) -> None:
    client, manager = _client(_ExplodingScanner, monkeypatch)

    resp = client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

    assert resp.status_code == 500
    assert manager.types() == ["library_scan_started", "library_scan_error"]
    # Class-name-only redaction: the OS path in the exception must not leak.
    err = manager.frames[-1]["data"]["error"]
    assert err == "ValueError during library scan"
    assert "/secret/path" not in err
