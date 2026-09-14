"""
Regression tests for the library-scan router's closure-to-module-level
extraction (#5166).

`create_library_scan_router()` was the last of the ten router factories still
shaped as one big closure: both of its handlers were nested `async def`s,
reachable only by constructing the whole router and then fishing the endpoint
back out of `router.routes`. They are now module-level `async def`s with
FastAPI `Depends()` defaults, following the pattern #4670 established in
`routers/player.py` -- a caller that wants to unit-test one just passes its
dependencies as keyword arguments, bypassing `Depends()`, `_LibraryScanDeps`
and the router entirely.

These tests pin both halves of that: the seam is real (direct calls work), and
the WIRING is unchanged (the factory still registers exactly the same paths and
methods the decorators used to).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.library_scan import (  # noqa: E402
    create_library_scan_router,
    get_scan_status,
    scan_library,
)

# The endpoint set the `@router.get`/`@router.post` decorators used to declare.
_EXPECTED_ROUTES = {
    ("/api/library/scan/status", ("GET",)),
    ("/api/library/scan", ("POST",)),
}


class TestHandlersAreCallableWithoutTheFactory:
    """The seam #5166 asked for."""

    @pytest.mark.asyncio
    async def test_get_scan_status_callable_with_a_bare_stub(self):
        """No router, no _LibraryScanDeps, no app -- just the handler."""
        stub = SimpleNamespace(is_scanning=lambda: True)

        assert await get_scan_status(library_database=stub) == {"is_scanning": True}

    @pytest.mark.asyncio
    async def test_get_scan_status_503s_on_a_missing_library_manager(self):
        """#4656's guard survives the extraction: the *resolved* manager is
        checked, so None reaches the client as a typed 503 rather than an
        opaque 500 from deeper in the scan."""
        with pytest.raises(HTTPException) as excinfo:
            await get_scan_status(library_database=None)

        assert excinfo.value.status_code == 503

    @pytest.mark.asyncio
    async def test_scan_library_503s_on_a_missing_library_manager(self):
        """Same guard on the scan handler, reached by direct call.

        `http_request=None` is the documented "no disconnect watcher" mode of
        `_await_scan`; the 503 fires long before it is consulted.
        """
        from schemas import LibraryScanRequest

        with pytest.raises(HTTPException) as excinfo:
            await scan_library(
                LibraryScanRequest(directories=[str(Path.cwd())]),
                None,  # type: ignore[arg-type]
                library_database=None,
                connection_manager=None,
            )

        assert excinfo.value.status_code == 503


class TestWiringIsUnchanged:
    """WIRING check: a dropped `add_api_route` would otherwise be silent."""

    def test_factory_registers_exactly_the_documented_endpoints(self):
        router = create_library_scan_router(lambda: SimpleNamespace())

        registered = {
            (r.path, tuple(sorted(r.methods))) for r in router.routes  # type: ignore[attr-defined]
        }
        assert registered == _EXPECTED_ROUTES

    def test_no_handler_is_nested_inside_the_factory_any_more(self):
        """The acceptance criterion, stated structurally so a future handler
        cannot quietly be added back inside the closure."""
        import ast
        import inspect

        import routers.library_scan as mod

        tree = ast.parse(inspect.getsource(mod))
        factory = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "create_library_scan_router"
        )
        nested = [
            child.name for child in ast.walk(factory)
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
            and child is not factory
        ]
        assert nested == [], (
            f"create_library_scan_router() nests {nested} again — #5166 "
            f"moved every handler to module level"
        )

    def test_factory_populates_the_dependency_holder(self):
        """RETURN VALUE check: a dependency the factory was given must not be
        silently None at request time."""
        from routers import library_scan

        manager = object()
        create_library_scan_router(lambda: "db", connection_manager=manager)

        assert library_scan._get_library_database() == "db"
        assert library_scan._get_connection_manager() is manager
