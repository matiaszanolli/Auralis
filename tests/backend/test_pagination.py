"""
Tests for shared pagination utilities.

Covers PaginatedResponse (factory method, has_more logic, field constraints)
and PaginationParams constants.
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

from routers.pagination import PaginatedResponse, PaginationParams, compute_has_more


# ---------------------------------------------------------------------------
# compute_has_more — the shared formula (#4902)
#
# Previously duplicated inline at 5 call sites (albums.py, artists.py,
# tracks.py x2, playlists.py); routers/pagination.py::PaginatedResponse was
# never imported by any of them despite its own docstring claiming it
# eliminated exactly this duplication. All 5 routers, plus
# PaginatedResponse.create() itself, now call this one function.
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
    def test_matches_paginated_response_create(self, offset, item_count, total, expected):
        """compute_has_more() and PaginatedResponse.create() must agree —
        the latter delegates to the former (#4902), so this is a regression
        guard against them drifting apart again."""
        items = list(range(item_count))
        resp = PaginatedResponse.create(items=items, total=total, limit=50, offset=offset)
        assert compute_has_more(offset, item_count, total) == expected
        assert resp.has_more == expected


# ---------------------------------------------------------------------------
# PaginatedResponse.create — has_more logic
# ---------------------------------------------------------------------------

class TestPaginatedResponseCreate:
    def test_has_more_true_when_more_items_remain(self):
        resp = PaginatedResponse.create(items=list(range(10)), total=25, limit=10, offset=0)
        assert resp.has_more is True

    def test_has_more_false_on_last_page(self):
        # offset=15, limit=10 → offset+limit=25 == total → no more
        resp = PaginatedResponse.create(items=list(range(10)), total=25, limit=10, offset=15)
        assert resp.has_more is False

    def test_has_more_false_when_past_total(self):
        resp = PaginatedResponse.create(items=[], total=5, limit=10, offset=10)
        assert resp.has_more is False

    def test_has_more_boundary_one_before_end(self):
        # offset=14, limit=10 → 24 < 25 → True
        resp = PaginatedResponse.create(items=list(range(10)), total=25, limit=10, offset=14)
        assert resp.has_more is True

    def test_has_more_false_empty_collection(self):
        resp = PaginatedResponse.create(items=[], total=0, limit=50, offset=0)
        assert resp.has_more is False

    def test_fields_round_trip(self):
        items = [{"id": 1}, {"id": 2}]
        resp = PaginatedResponse.create(items=items, total=100, limit=2, offset=10)
        assert resp.items == items
        assert resp.total == 100
        assert resp.limit == 2
        assert resp.offset == 10

    def test_single_item_total(self):
        resp = PaginatedResponse.create(items=["a"], total=1, limit=50, offset=0)
        assert resp.has_more is False
        assert resp.total == 1

    def test_first_page_of_many(self):
        resp = PaginatedResponse.create(items=list(range(50)), total=500, limit=50, offset=0)
        assert resp.has_more is True

    def test_exact_full_page_no_remainder(self):
        # 200 items, limit=50, offset=150 → offset+limit=200 == total → no more
        resp = PaginatedResponse.create(items=list(range(50)), total=200, limit=50, offset=150)
        assert resp.has_more is False

    def test_items_can_be_arbitrary_types(self):
        resp = PaginatedResponse.create(items=["x", "y"], total=2, limit=10, offset=0)
        assert resp.items == ["x", "y"]


# ---------------------------------------------------------------------------
# PaginatedResponse field validation (Pydantic ge= constraints)
# ---------------------------------------------------------------------------

class TestPaginatedResponseValidation:
    def test_total_cannot_be_negative(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PaginatedResponse(items=[], total=-1, offset=0, limit=10, has_more=False)

    def test_offset_cannot_be_negative(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PaginatedResponse(items=[], total=0, offset=-1, limit=10, has_more=False)

    def test_limit_cannot_be_zero(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PaginatedResponse(items=[], total=0, offset=0, limit=0, has_more=False)

    def test_limit_cannot_be_negative(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PaginatedResponse(items=[], total=0, offset=0, limit=-5, has_more=False)

    def test_valid_minimum_values_accepted(self):
        resp = PaginatedResponse(items=[], total=0, offset=0, limit=1, has_more=False)
        assert resp.limit == 1
        assert resp.offset == 0
        assert resp.total == 0


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
