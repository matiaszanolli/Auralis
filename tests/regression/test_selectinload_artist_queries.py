"""
Selectinload Artist Queries Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #2613:
All ArtistRepository query methods must use selectinload (not joinedload)
to avoid N*M Cartesian-product row explosion.
"""

import inspect
import re

import pytest

from auralis.library.repositories.artist_repository import ArtistRepository


@pytest.mark.regression
class TestSelectinloadArtistQueries:
    """Verify ArtistRepository uses selectinload, not joinedload (#2613)."""

    def _get_source(self, method_name: str) -> str:
        method = getattr(ArtistRepository, method_name)
        return inspect.getsource(method)

    def _has_joinedload_call(self, source: str) -> bool:
        """Check for actual joinedload() function calls, ignoring comments."""
        code_lines = [
            line for line in source.splitlines()
            if not line.strip().startswith('#')
        ]
        code_only = '\n'.join(code_lines)
        return bool(re.search(r'\bjoinedload\s*\(', code_only))

    def test_get_all_uses_selectinload(self):
        src = self._get_source('get_all')
        assert 'selectinload(' in src, "get_all() should use selectinload"
        assert not self._has_joinedload_call(src), "get_all() should not use joinedload"

    def test_get_by_id_uses_selectinload(self):
        src = self._get_source('get_by_id')
        assert 'selectinload(' in src, "get_by_id() should use selectinload"
        assert not self._has_joinedload_call(src), "get_by_id() should not use joinedload"

    def test_search_uses_selectinload(self):
        src = self._get_source('search')
        assert 'selectinload(' in src, "search() should use selectinload"
        assert not self._has_joinedload_call(src), "search() should not use joinedload"

    def test_get_by_name_uses_selectinload(self):
        src = self._get_source('get_by_name')
        assert 'selectinload(' in src, "get_by_name() should use selectinload"
        assert not self._has_joinedload_call(src), "get_by_name() should not use joinedload"
