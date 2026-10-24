"""
Tests for shared pagination utilities.

Covers compute_has_more() and PaginationParams constants. PaginatedResponse
(the generic response model this file used to also cover) was deleted in
#5054 — zero routers ever imported it (the residual, never-adopted half of
#4902); see routers/pagination.py::compute_has_more's docstring for why.
"""

import sys
import types
from pathlib import Path

import pytest

_backend_dir = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
sys.path.insert(0, str(_backend_dir))

# Import routers utilities directly without triggering routers/__init__.py
# (which causes a circular import: player -> services -> config -> player).
if 'routers' not in sys.modules:
    _stub = types.ModuleType('routers')
    _stub.__path__ = [str(_backend_dir / 'routers')]
    _stub.__package__ = 'routers'
    sys.modules['routers'] = _stub

from routers.pagination import (
    PaginationParams,
    compute_has_more,
    limit_query,
    offset_query,
    paginated,
)


# ---------------------------------------------------------------------------
# compute_has_more — the shared formula (#4902)
#
# Previously duplicated inline at 5 call sites (albums.py, artists.py,
# tracks.py x2, playlists.py); all 5 now call this one function directly.
# The generic PaginatedResponse model this file used to also cover was
# deleted (#5054) — zero routers ever imported it.
# ---------------------------------------------------------------------------

class TestComputeHasMore:
    def test_true_when_more_items_remain(self):
        assert compute_has_more(offset=0, item_count=10, total=25) is True

    def test_false_on_last_page(self):
        assert compute_has_more(offset=15, item_count=10, total=25) is False

    def test_false_when_past_total(self):
        assert compute_has_more(offset=10, item_count=0, total=5) is False

    def test_boundary_one_before_end(self):
        assert compute_has_more(offset=14, item_count=10, total=25) is True

    def test_false_on_exact_full_page_no_remainder(self):
        assert compute_has_more(offset=150, item_count=50, total=200) is False

    def test_false_on_empty_collection(self):
        assert compute_has_more(offset=0, item_count=0, total=0) is False

    @pytest.mark.parametrize(
        "offset,item_count,total,expected",
        [
            (0, 50, 500, True),
            (0, 1, 1, False),
            (450, 50, 500, False),
            (449, 50, 500, True),
            (0, 0, 0, False),
        ],
    )
    def test_has_more_matrix(self, offset, item_count, total, expected):
        assert compute_has_more(offset, item_count, total) == expected


# ---------------------------------------------------------------------------
# PaginationParams constants
# ---------------------------------------------------------------------------

class TestPaginationParamsConstants:
    def test_default_limit(self):
        assert PaginationParams.DEFAULT_LIMIT == 50

    def test_max_limit(self):
        assert PaginationParams.MAX_LIMIT == 200

    def test_min_limit(self):
        assert PaginationParams.MIN_LIMIT == 1

    def test_default_offset(self):
        assert PaginationParams.DEFAULT_OFFSET == 0

    def test_min_offset(self):
        assert PaginationParams.MIN_OFFSET == 0

    def test_max_limit_greater_than_default(self):
        assert PaginationParams.MAX_LIMIT > PaginationParams.DEFAULT_LIMIT

    def test_min_limit_less_than_default(self):
        assert PaginationParams.MIN_LIMIT < PaginationParams.DEFAULT_LIMIT


class TestRouterQueryReferencesTheCanonicalCap:
    """#4761/#6222 regression guard: routers must build their limit/offset
    Query parameters through pagination.limit_query()/offset_query(), not
    spell Query(PaginationParams.DEFAULT_LIMIT, ge=..., le=...) inline — a
    spelled-out copy can silently drift from the canonical bounds (and did:
    five copies across four routers). schemas.PaginationParams (a second,
    incompatible class capped at 500) was deleted for the same reason — two
    definitions of "the" pagination cap is exactly how a drift like that
    goes unnoticed."""

    @pytest.mark.parametrize("router_module", ["albums", "artists", "tracks", "playlists_crud"])
    def test_query_declarations_reference_max_limit_by_name(self, router_module):
        import inspect
        import importlib

        source = inspect.getsource(importlib.import_module(f"routers.{router_module}"))
        assert "PaginationParams.MAX_LIMIT" not in source, (
            f"routers/{router_module}.py spells pagination bounds inline — use "
            "pagination.limit_query()/offset_query() instead (#6222)"
        )
        assert "PaginationParams." not in source, (
            f"routers/{router_module}.py references PaginationParams directly — the "
            "canonical entry points are pagination.limit_query()/offset_query() (#6222)"
        )


class TestLimitOffsetQueryFactories:
    """#6222: the factories produce exactly the Query parameters the five
    paginated endpoints previously spelled inline — same defaults, same
    bounds, optional description preserved. Asserted through the OpenAPI
    schema because that is the wire contract (and FastAPI's Query stores
    ge/le as metadata, not attributes)."""

    def _param_schema(self, app, path, name):
        schema = app.openapi()["paths"][path]["get"]
        return next(p for p in schema["parameters"] if p["name"] == name)

    def test_factory_bounds_and_default(self):
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/probe")
        async def probe(
            limit: int = limit_query(),
            offset: int = offset_query(),
        ):
            return {}

        limit_p = self._param_schema(app, "/probe", "limit")
        offset_p = self._param_schema(app, "/probe", "offset")
        assert limit_p["schema"] == {"default": 50, "minimum": 1, "maximum": 200, "type": "integer", "title": "Limit"}
        assert offset_p["schema"]["default"] == 0 and offset_p["schema"]["minimum"] == 0
        assert "maximum" not in offset_p["schema"] or offset_p["schema"].get("maximum") is None
        assert "description" not in limit_p and "description" not in offset_p

    def test_factory_description_passthrough(self):
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/probe")
        async def probe(
            limit: int = limit_query("Number of artists to return"),
            offset: int = offset_query("Number of artists to skip"),
        ):
            return {}

        assert self._param_schema(app, "/probe", "limit")["description"] == "Number of artists to return"
        assert self._param_schema(app, "/probe", "offset")["description"] == "Number of artists to skip"


class TestPaginatedEnvelope:
    """#6222: one spelling of the page envelope, with has_more from
    compute_has_more so partial last pages work."""

    def test_envelope_keys_and_has_more(self):
        env = paginated("tracks", [1, 2, 3], total=10, offset=0, limit=3)
        assert env == {
            "tracks": [1, 2, 3],
            "total": 10,
            "offset": 0,
            "limit": 3,
            "has_more": True,
        }

    def test_partial_last_page_has_more_false(self):
        assert paginated("albums", [1, 2], total=5, offset=3, limit=3)["has_more"] is False
