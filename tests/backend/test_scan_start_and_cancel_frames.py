"""Scan start/terminal WS frame ordering (#4602, #4603).

**#4602** — the routers broadcast `library_scan_started` unconditionally on
entry, before `scan_directories()` ran and long before `result.rejected` could
be known. A second scan requested while one was in flight got its 409, but the
start frame had already gone out, and `useScanProgress` resets to INITIAL_STATE
on that frame — wiping the live counters of the scan actually running. On a
large library that is minutes of actively misleading UI, unrecoverable short of
waiting out the original scan. The scanner now reports a `stage: 'started'`
progress event once it owns the scan slot, and both emitters (manual route and
auto-scanner, which had the identical bug) translate that into the frame.

**#4603** — `asyncio.CancelledError` derives from `BaseException`, so the
handler's `except Exception` never caught it and there was no `finally`: a
cancelled scan left with NO terminal frame. `useScanProgress` clears
`isScanning` only on `scan_complete`/`library_scan_error`, so the panel stayed
"Scanning…" for the rest of the session with tracks half-imported. The frontend
cancels this request on unmount and on supersede.
"""

import asyncio
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers.library_scan import create_library_scan_router  # noqa: E402


class _CapturingManager:
    def __init__(self) -> None:
        self.frames: list[dict] = []

    async def broadcast(self, message: dict) -> None:
        self.frames.append(message)

    def types(self) -> list:
        return [f.get("type") for f in self.frames]


class _BaseScanner:
    """Fake scanner that reports `started` only when it 'owns the slot'."""

    def __init__(self, _manager) -> None:
        self._cb = None

    def set_progress_callback(self, cb) -> None:
        self._cb = cb

    def _report(self, payload) -> None:
        if self._cb:
            self._cb(payload)

    def stop_scan(self) -> None:
        pass


class _RejectingScanner(_BaseScanner):
    """A scan the concurrency guard rejects — reports NO start event."""

    def scan_directories(self, directories=(), **_kwargs):
        return SimpleNamespace(
            rejected=True, added_tracks=[], files_found=0, files_processed=0,
            files_added=0, files_updated=0, files_skipped=0, files_failed=0,
            scan_time=0.0, directories_scanned=0,
            # #4841: the router serialises result.failures.
            failures=[],
        )


class _AcceptingScanner(_BaseScanner):
    """A scan that is accepted — reports start, then progress, then finishes."""

    def scan_directories(self, directories=(), **_kwargs):
        self._report({'stage': 'started', 'directories': list(directories)})
        self._report({'stage': 'processing', 'processed': 3, 'total_found': 10})
        return SimpleNamespace(
            rejected=False, added_tracks=[], files_found=10, files_processed=10,
            files_added=2, files_updated=0, files_skipped=8, files_failed=0,
            scan_time=1.5, directories_scanned=1,
            failures=[],
        )


class _CancelledScanner(_BaseScanner):
    """Blocks so the request task can be cancelled mid-scan."""

    def __init__(self, _manager) -> None:
        super().__init__(_manager)
        self._stop = threading.Event()

    def scan_directories(self, directories=(), **_kwargs):
        self._report({'stage': 'started', 'directories': list(directories)})
        self._stop.wait(timeout=10)
        return SimpleNamespace(rejected=False, added_tracks=[])

    def stop_scan(self) -> None:
        self._stop.set()


def _client(scanner_cls, monkeypatch):
    import auralis.library.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "LibraryScanner", scanner_cls)
    manager = _CapturingManager()
    app = FastAPI()
    app.include_router(
        create_library_scan_router(lambda: SimpleNamespace(), connection_manager=manager)
    )
    return TestClient(app, raise_server_exceptions=False), manager


class TestRejectedScanEmitsNoStartFrame:
    """#4602 — the core regression."""

    def test_409_scan_broadcasts_nothing(self, monkeypatch, tmp_path) -> None:
        client, manager = _client(_RejectingScanner, monkeypatch)

        resp = client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

        assert resp.status_code == 409
        assert manager.types() == [], (
            "a rejected scan must not announce a start — the frame resets the "
            "running scan's counters in useScanProgress (#4602)"
        )

    def test_rejected_scan_does_not_emit_a_terminal_frame_either(
        self, monkeypatch, tmp_path
    ) -> None:
        """The 409 path must not tear down the running scan's UI either."""
        client, manager = _client(_RejectingScanner, monkeypatch)

        client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

        assert "library_scan_error" not in manager.types()
        assert "scan_complete" not in manager.types()


class TestAcceptedScanStillAnnouncesStart:
    def test_exactly_one_start_frame_then_complete(self, monkeypatch, tmp_path) -> None:
        client, manager = _client(_AcceptingScanner, monkeypatch)

        resp = client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

        assert resp.status_code == 200
        types = manager.types()
        assert types.count("library_scan_started") == 1
        assert types[0] == "library_scan_started"
        assert "scan_complete" in types

    def test_start_frame_carries_the_directories(self, monkeypatch, tmp_path) -> None:
        client, manager = _client(_AcceptingScanner, monkeypatch)

        client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

        start = next(f for f in manager.frames if f["type"] == "library_scan_started")
        assert start["data"]["directories"] == [str(tmp_path)]

    def test_started_event_is_not_also_sent_as_scan_progress(
        self, monkeypatch, tmp_path
    ) -> None:
        """No double-fire: the started event becomes exactly one frame."""
        client, manager = _client(_AcceptingScanner, monkeypatch)

        client.post("/api/library/scan", json={"directories": [str(tmp_path)]})

        progress = [f for f in manager.frames if f["type"] == "scan_progress"]
        assert len(progress) == 1
        assert progress[0]["data"]["phase"] == "processing"


class TestCancellationEmitsTerminalFrame:
    """#4603 — cancelled scans must release the UI."""

    @pytest.mark.asyncio
    async def test_cancelled_scan_broadcasts_error_and_reraises(
        self, monkeypatch, tmp_path
    ) -> None:
        import auralis.library.scanner as scanner_mod

        monkeypatch.setattr(scanner_mod, "LibraryScanner", _CancelledScanner)
        manager = _CapturingManager()
        router = create_library_scan_router(
            lambda: SimpleNamespace(), connection_manager=manager
        )
        # Reach the handler directly: TestClient runs the request on its own
        # portal, which makes cancelling the request task from here unreliable.
        handler = next(
            r.endpoint for r in router.routes if getattr(r, "path", "") == "/api/library/scan"
        )
        from schemas import LibraryScanRequest

        task = asyncio.create_task(
            handler(LibraryScanRequest(directories=[str(tmp_path)]))
        )
        # Let the scan reach its blocking wait, then cancel.
        for _ in range(50):
            await asyncio.sleep(0.01)
            if any(f["type"] == "library_scan_started" for f in manager.frames):
                break
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        types = manager.types()
        assert "library_scan_error" in types, (
            "a cancelled scan left no terminal frame, so useScanProgress kept "
            "isScanning=true for the rest of the session (#4603)"
        )
        assert types.count("library_scan_error") == 1

    def test_source_orders_cancelled_before_generic_exception(self) -> None:
        """White-box: `except Exception` cannot catch a BaseException.

        Ordering matters for readability and for the next person adding a
        handler; pin that the clause exists and precedes the generic one.
        """
        import inspect

        import routers.library_scan as mod

        src = inspect.getsource(mod)
        cancelled_at = src.index("except asyncio.CancelledError:\n            # The one exit")
        generic_at = src.index("except Exception as e:")
        assert cancelled_at < generic_at

    def test_timeout_path_unaffected(self) -> None:
        """TimeoutError is an Exception subclass and keeps its own handler."""
        assert issubclass(asyncio.TimeoutError, Exception)
        assert not issubclass(asyncio.CancelledError, Exception)
