"""
Regression tests for the settings router's closure-to-module-level extraction
(#5832).

`create_settings_router()` was a 223-line closure whose five endpoints were
nested `async def`s. They are now module-level handlers with `Depends()`
defaults (the #4670 / #5166 pattern), and the factory only assembles. These
tests pin that the seam is real and that the registered `(path, methods)` set
is the one the decorators used to declare.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.settings import (  # noqa: E402
    create_settings_router,
    get_settings,
    reset_settings,
)

_EXPECTED_ROUTES = {
    ("/api/settings", ("GET",)),
    ("/api/settings", ("PUT",)),
    ("/api/settings/scan-folders", ("POST",)),
    ("/api/settings/scan-folders/delete", ("POST",)),
    ("/api/settings/reset", ("POST",)),
}


class TestHandlersAreCallableWithoutTheFactory:
    @pytest.mark.asyncio
    async def test_get_settings_with_a_bare_stub_repo(self):
        stub = SimpleNamespace(
            get_settings=lambda: SimpleNamespace(to_dict=lambda: {"theme": "dark"})
        )

        assert await get_settings(repo=stub) == {"theme": "dark"}

    @pytest.mark.asyncio
    async def test_get_settings_404s_when_no_row_exists(self):
        stub = SimpleNamespace(get_settings=lambda: None)

        with pytest.raises(HTTPException) as excinfo:
            await get_settings(repo=stub)

        assert excinfo.value.status_code == 404

    @pytest.mark.asyncio
    async def test_reset_settings_with_no_optional_collaborators(self):
        from routers.settings_deps import _SettingsDeps

        stub = SimpleNamespace(
            reset_to_defaults=lambda: SimpleNamespace(to_dict=lambda: {"theme": "auto"})
        )

        result = await reset_settings(repo=stub, deps=_SettingsDeps())

        assert result["settings"] == {"theme": "auto"}


class TestWiringIsUnchanged:
    def test_factory_registers_exactly_the_documented_endpoints(self):
        router = create_settings_router(lambda: SimpleNamespace())

        registered = {
            (route.path, tuple(sorted(route.methods)))  # type: ignore[attr-defined]
            for route in router.routes
        }

        assert registered == _EXPECTED_ROUTES

    def test_missing_repo_is_a_typed_503(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(create_settings_router(lambda: None))

        assert TestClient(app).get("/api/settings").status_code == 503

    def test_two_routers_do_not_share_a_repository(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        def repo(theme):
            return SimpleNamespace(
                get_settings=lambda: SimpleNamespace(to_dict=lambda: {"theme": theme})
            )

        first, second = FastAPI(), FastAPI()
        first.include_router(create_settings_router(lambda: repo("one")))
        second.include_router(create_settings_router(lambda: repo("two")))

        # response_model fills the unset fields, so compare the one that differs.
        assert TestClient(first).get("/api/settings").json()["theme"] == "one"
        assert TestClient(second).get("/api/settings").json()["theme"] == "two"
