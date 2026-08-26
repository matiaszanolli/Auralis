"""
Regression: router factories build a fresh APIRouter per call (#4361)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

routers/library.py and routers/system.py used to create their APIRouter at
MODULE scope and decorate handlers onto it inside the factory, unlike the
isolated per-factory pattern every other router uses (metadata.py:87
documents "fresh router ... avoids route pollution"). No production effect
(each factory runs once at startup), but a second factory call — a test
building the app twice, or a future refactor — would re-register or shadow
routes on the SAME shared object, and any dependency bound on that second
call would silently never take effect (FastAPI serves the first-registered
handler).

At the time this issue was fixed, 6 of the original 8 cited files (player,
playlists, enhancement, artwork, files, wav_streaming) had already been
migrated to the isolated pattern by unrelated work; only library.py and
system.py remained.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from fastapi import APIRouter

from routers.library import create_library_router
from routers.system import create_system_router


def test_no_router_module_defines_a_module_scope_router():
    """Static check matching the issue's own Completeness Check:
    grep -rn '^router = APIRouter' auralis-web/backend/routers/ must be empty."""
    routers_dir = Path(__file__).resolve().parents[2] / "auralis-web" / "backend" / "routers"
    offenders = []
    for path in routers_dir.glob("*.py"):
        for line in path.read_text().splitlines():
            if line.startswith("router = APIRouter"):
                offenders.append(path.name)
    assert offenders == [], f"module-scope router(s) found in: {offenders}"


class TestLibraryRouterFactoryIsolation:
    def test_two_calls_return_distinct_router_objects(self):
        router_a = create_library_router(get_repository_factory=MagicMock())
        router_b = create_library_router(get_repository_factory=MagicMock())

        assert router_a is not router_b
        assert router_a.routes is not router_b.routes

    def test_each_call_registers_its_own_independent_routes(self):
        router_a = create_library_router(get_repository_factory=MagicMock())
        router_b = create_library_router(get_repository_factory=MagicMock())

        paths_a = {r.path for r in router_a.routes}
        paths_b = {r.path for r in router_b.routes}
        assert paths_a == paths_b  # same route set...
        assert paths_a  # ...but not empty

        # ...and NOT a single shared list that both calls appended onto:
        # a fresh router per call means neither's route count doubled.
        assert len(router_a.routes) == len(router_b.routes)


class TestSystemRouterFactoryIsolation:
    def _build(self) -> APIRouter:
        return create_system_router(
            manager=MagicMock(),
            get_processing_engine=MagicMock(),
            HAS_AURALIS=True,
        )

    def test_two_calls_return_distinct_router_objects(self):
        router_a = self._build()
        router_b = self._build()

        assert router_a is not router_b
        assert router_a.routes is not router_b.routes

    def test_each_call_registers_its_own_websocket_route_only_once(self):
        router_a = self._build()
        router_b = self._build()

        # A shared module-level router would double up on every re-call
        # (two /ws routes registered on the same object after two calls).
        assert len(router_a.routes) == 1
        assert len(router_b.routes) == 1
