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
"Scanning…" for the rest of the session with tracks half-imported.

**#4820** — and the frontend's unmount/supersede aborts never produced that
cancellation in the first place. The handler took only the parsed body, so it
could not observe `is_disconnected()`, and closing a fetch does not cancel an
already-scheduled route coroutine: the scan ran on to completion or its 1-hour
timeout, holding the single scan slot and 409-ing every scan the user started
afterwards. The handler now takes the ASGI `Request` too and races the scanner
thread against a disconnect watcher.
"""

import asyncio
import sys
import threading
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from routers import library_scan  # noqa: E402
from routers.library_scan import create_library_scan_router  # noqa: E402
from schemas import LibraryScanRequest  # noqa: E402


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

    #: Every instance built by the router, so a test can inspect the scanner
    #: the handler actually created (#4820).
    instances: list = []

    def __init__(self, _manager) -> None:
        super().__init__(_manager)
        self._stop = threading.Event()
        self.stopped = False
        _CancelledScanner.instances.append(self)

    def scan_directories(self, directories=(), **_kwargs):
        self._report({'stage': 'started', 'directories': list(directories)})
        self._stop.wait(timeout=10)
        return SimpleNamespace(rejected=False, added_tracks=[])

    def stop_scan(self) -> None:
        self.stopped = True
        self._stop.set()


class _FakeRequest:
    """Stand-in for the ASGI Request: the handler only uses its receive channel.

    With `disconnect_after` the channel yields `http.disconnect` after that many
    seconds, like a server whose client closed the connection. The default never
    disconnects, so a test can prove a connected client's scan is not aborted.
    """

    def __init__(self, disconnect_after: float | None = None) -> None:
        self.disconnect_after = disconnect_after
        self.receives = 0

    async def receive(self):
        self.receives += 1
        if self.disconnect_after is None:
            await asyncio.Event().wait()  # never returns; cancelled by the handler
        await asyncio.sleep(self.disconnect_after)
        return {"type": "http.disconnect"}


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
        # Reach the handler directly: TestClient runs the request on its own
        # portal, which makes cancelling the request task from here unreliable.
        # #5166 made scan_library a module-level `async def`, so its
        # dependencies are passed as plain keyword arguments -- no router, no
        # Depends() resolution, no _LibraryScanDeps.
        handler = partial(
            library_scan.scan_library,
            library_database=SimpleNamespace(),
            connection_manager=manager,
        )
        task = asyncio.create_task(
            handler(LibraryScanRequest(directories=[str(tmp_path)]), _FakeRequest())
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
        cancelled_at = src.index("except asyncio.CancelledError:\n        # The one exit")
        generic_at = src.index("except Exception as e:")
        assert cancelled_at < generic_at

    def test_timeout_path_unaffected(self) -> None:
        """TimeoutError is an Exception subclass and keeps its own handler."""
        assert issubclass(asyncio.TimeoutError, Exception)
        assert not issubclass(asyncio.CancelledError, Exception)


def _scan_handler(monkeypatch, scanner_cls):
    """The bare handler plus a frame-capturing manager (no TestClient).

    TestClient runs the request on its own portal, which makes both cancelling
    the request task and faking a disconnect unreliable.
    """
    import auralis.library.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "LibraryScanner", scanner_cls)
    manager = _CapturingManager()
    # #5166: the handler is module level, so its dependencies are ordinary
    # keyword arguments rather than closure captures inside the factory.
    handler = partial(
        library_scan.scan_library,
        library_database=SimpleNamespace(),
        connection_manager=manager,
    )
    return handler, manager


class TestClientDisconnectStopsTheScan:
    """#4820 — an aborted fetch has to reach the scanner thread."""

    @pytest.fixture(autouse=True)
    def _clean_scanner_registry(self):
        _CancelledScanner.instances.clear()
        yield
        _CancelledScanner.instances.clear()

    @pytest.mark.asyncio
    async def test_disconnect_stops_the_scanner_and_returns_499(
        self, monkeypatch, tmp_path
    ) -> None:
        from fastapi import HTTPException

        handler, manager = _scan_handler(monkeypatch, _CancelledScanner)

        with pytest.raises(HTTPException) as excinfo:
            await handler(
                LibraryScanRequest(directories=[str(tmp_path)]),
                _FakeRequest(disconnect_after=0.01),
            )

        assert excinfo.value.status_code == 499
        assert _CancelledScanner.instances, "handler never built a scanner"
        assert _CancelledScanner.instances[0].stopped, (
            "the abort never reached scanner.stop_scan(), so the scan kept "
            "running and kept the scan slot (#4820)"
        )

    @pytest.mark.asyncio
    async def test_disconnect_emits_a_terminal_frame(self, monkeypatch, tmp_path) -> None:
        """The WebSocket outlives the aborted fetch, so the UI still needs to
        be told to leave the scanning state."""
        from fastapi import HTTPException

        handler, manager = _scan_handler(monkeypatch, _CancelledScanner)

        with pytest.raises(HTTPException):
            await handler(
                LibraryScanRequest(directories=[str(tmp_path)]),
                _FakeRequest(disconnect_after=0.01),
            )

        assert manager.types().count("library_scan_error") == 1
        assert "scan_complete" not in manager.types()

    @pytest.mark.asyncio
    async def test_connected_client_scan_completes_normally(
        self, monkeypatch, tmp_path
    ) -> None:
        """The watcher must not abort a scan whose client is still there."""
        handler, manager = _scan_handler(monkeypatch, _AcceptingScanner)

        result = await handler(
            LibraryScanRequest(directories=[str(tmp_path)]), _FakeRequest()
        )

        assert result.files_added == 2
        assert "scan_complete" in manager.types()

    @pytest.mark.asyncio
    async def test_watcher_task_is_not_orphaned(self, monkeypatch, tmp_path) -> None:
        """RETURN VALUE check (#4820): a normally-completing scan leaves no
        polling task behind."""
        handler, _manager = _scan_handler(monkeypatch, _AcceptingScanner)
        before = asyncio.all_tasks()

        await handler(LibraryScanRequest(directories=[str(tmp_path)]), _FakeRequest())
        # Give a cancelled watcher a chance to actually finish, so a leak shows
        # up as a live task rather than a scheduling artefact.
        await asyncio.sleep(0)

        leaked = [
            t for t in asyncio.all_tasks() - before
            if not t.done() and "_watch_for_disconnect" in repr(t.get_coro())
        ]
        assert leaked == [], f"orphaned disconnect watcher: {leaked}"


class TestScanHandlerTakesTheAsgiRequest:
    """#4820 — the signature is the fix: a body model alone cannot observe a
    disconnect."""

    def test_handler_accepts_a_request_parameter(self) -> None:
        import inspect

        import routers.library_scan as mod
        from fastapi import Request

        router = mod.create_library_scan_router(lambda: SimpleNamespace())
        handler = next(
            r.endpoint for r in router.routes if getattr(r, "path", "") == "/api/library/scan"
        )
        params = inspect.signature(handler).parameters
        assert params["http_request"].annotation is Request


class TestDisconnectSurvivesTheMiddlewareStack:
    """The trap this fix nearly fell into.

    `Request.is_disconnected()` peeks at the receive channel from an
    already-cancelled anyio scope. Every BaseHTTPMiddleware layer (this app
    stacks four) wraps `receive` in a task group whose exit swallows the
    message under that cancellation, so the poll answers "still connected"
    forever — a handler-level unit test passes while production never detects
    anything. These drive raw ASGI through real middleware to pin the
    difference.
    """

    @staticmethod
    def _probe_app(watch):
        """A FastAPI app behind four BaseHTTPMiddleware layers whose route
        reports whether `watch(request)` noticed the disconnect."""
        from fastapi import FastAPI, Request
        from starlette.middleware.base import BaseHTTPMiddleware

        class _PassThrough(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                return await call_next(request)

        app = FastAPI()
        for _ in range(4):
            app.add_middleware(_PassThrough)
        seen: dict = {}

        @app.post("/probe")
        async def probe(payload: dict, request: Request):  # noqa: ANN202
            watcher = asyncio.ensure_future(watch(request))
            done, _pending = await asyncio.wait({watcher}, timeout=2.0)
            seen["detected"] = watcher in done
            if not watcher.done():
                watcher.cancel()
            return {"ok": True}

        return app, seen

    @staticmethod
    async def _drive(app) -> None:
        """One POST whose client disconnects 0.05s after the body."""
        import json

        body = json.dumps({"a": 1}).encode()
        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": "/probe", "raw_path": b"/probe", "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"testserver"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
            "client": ("127.0.0.1", 1234), "server": ("127.0.0.1", 8765),
        }
        sent = False

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            await asyncio.sleep(0.05)
            return {"type": "http.disconnect"}

        async def send(_message) -> None:
            return None

        await asyncio.wait_for(app(scope, receive, send), timeout=10)

    @pytest.mark.asyncio
    async def test_the_shipped_watcher_detects_a_disconnect(self) -> None:
        import routers.library_scan as mod

        app, seen = self._probe_app(mod._watch_for_disconnect)
        await self._drive(app)

        assert seen["detected"] is True, (
            "the disconnect watcher must work through BaseHTTPMiddleware — "
            "this is the whole of #4820"
        )

    @pytest.mark.asyncio
    async def test_is_disconnected_polling_would_not_have_worked(self) -> None:
        """Regression guard: do not 'simplify' the watcher back to polling."""

        async def poll(request) -> None:
            while True:
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.01)

        app, seen = self._probe_app(poll)
        await self._drive(app)

        assert seen["detected"] is False
