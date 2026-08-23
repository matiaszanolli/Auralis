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

from routers.pagination import PaginationParams, compute_has_more


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
    """#4761 regression guard: routers must reference PaginationParams.MAX_LIMIT,
    not a bare literal that happens to match today and can silently drift
    tomorrow. schemas.PaginationParams (a second, incompatible class capped at
    500) was deleted for the same reason — two definitions of "the" pagination
    cap is exactly how a drift like that goes unnoticed."""

    @pytest.mark.parametrize("router_module", ["albums", "artists", "tracks", "playlists"])
    def test_query_declarations_reference_max_limit_by_name(self, router_module):
        import inspect
        import importlib

        source = inspect.getsource(importlib.import_module(f"routers.{router_module}"))
        assert "PaginationParams.MAX_LIMIT" in source, (
            f"routers/{router_module}.py must reference PaginationParams.MAX_LIMIT "
            "in its Query(...) declarations rather than a hardcoded literal"
        )
