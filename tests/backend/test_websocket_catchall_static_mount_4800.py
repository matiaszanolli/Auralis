"""Regression test for #4800.

In production (non-`--dev`) builds, `main.py` mounts `StaticFiles` at "/".
Starlette's `Mount` matches websocket scopes exactly like http ones (it only
discriminates on path, not `scope["type"]`), so an upgrade to any
unregistered `/ws*` path used to fall through the single real `/ws` route
all the way to the mount, whose `StaticFiles.__call__` asserts
`scope["type"] == "http"` and raises an unhandled `AssertionError` instead
of a clean close.

This test builds a minimal app with the same registration order as
`main.py` (real `/ws` route -> catch-all `/{path:path}` websocket route ->
`StaticFiles` mount at "/") to verify the fix at the Starlette-routing
level, independent of whether a built frontend `dist/` exists in the test
environment (main.py's own production-mount branch is only reachable when
one does).
"""

import sys
import tempfile
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi import FastAPI, WebSocket  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette import status  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402


def _build_app(static_dir: str, with_catchall: bool) -> FastAPI:
    app = FastAPI()

    @app.websocket("/ws")
    async def real_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text("hello")
        await websocket.close()

    if with_catchall:
        @app.websocket("/{path:path}")
        async def catch_all(websocket: WebSocket) -> None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)

    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    return app


@pytest.fixture
def static_dir():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "index.html").write_text("<html><body>ok</body></html>")
        yield tmp


def test_unregistered_ws_path_raises_without_catchall(static_dir):
    """Reproduces the bug: without the catch-all, an unregistered /ws* path
    falls through to the StaticFiles Mount and blows up with an
    AssertionError instead of a clean close."""
    app = _build_app(static_dir, with_catchall=False)
    client = TestClient(app, raise_server_exceptions=True)

    with pytest.raises(AssertionError):
        with client.websocket_connect("/ws/nope"):
            pass


def test_unregistered_ws_path_closes_cleanly_with_catchall(static_dir):
    """#4800 fix: the catch-all intercepts before the Mount is reached."""
    app = _build_app(static_dir, with_catchall=True)
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/nope"):
            pass
    assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION


def test_real_ws_route_still_works_with_catchall(static_dir):
    """The catch-all must not shadow the real /ws route registered before it."""
    app = _build_app(static_dir, with_catchall=True)
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        assert ws.receive_text() == "hello"


def test_http_static_serving_unaffected_by_catchall(static_dir):
    """Adding the websocket catch-all must not change HTTP StaticFiles
    behavior at "/"."""
    app = _build_app(static_dir, with_catchall=True)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "ok" in response.text
