"""
Regression tests for the system router's closure-to-module-level extraction
(#5832).

`create_system_router()` nested a 147-line `websocket_endpoint` closure. It is
now a module-level handler reaching its collaborators through `Depends()` and
`RouterDeps`; the factory only registers the route.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import contextlib
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from routers.system import create_system_router, websocket_endpoint  # noqa: E402


def test_endpoint_is_a_module_level_coroutine():
    import inspect

    assert inspect.iscoroutinefunction(websocket_endpoint)
    assert "deps" in inspect.signature(websocket_endpoint).parameters


def test_factory_registers_exactly_the_ws_route():
    router = create_system_router(SimpleNamespace(), lambda: None)

    assert {route.path for route in router.routes} == {"/ws"}


def test_two_routers_do_not_share_a_connection_manager():
    """RouterDeps keeps a second factory call from repointing the first."""
    seen = []

    def make(label):
        app = FastAPI()
        app.include_router(
            create_system_router(SimpleNamespace(label=label), lambda: None)
        )
        return app

    first = make("one")
    make("two")

    from routers import system as system_module

    original = system_module.ws_connection.setup_connection

    async def spy(websocket, manager, *a, **k):
        seen.append(manager.label)
        await websocket.close()  # reject the handshake so the client returns
        raise RuntimeError("stop after capturing the manager")

    system_module.ws_connection.setup_connection = spy
    try:
        with contextlib.suppress(Exception), TestClient(first).websocket_connect("/ws"):
            pass
    finally:
        system_module.ws_connection.setup_connection = original

    assert seen == ["one"]
