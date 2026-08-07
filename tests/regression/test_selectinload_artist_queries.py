"""
Selectinload Artist Queries Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #2613:
All ArtistRepository query methods must use selectinload (not joinedload)
to avoid N*M Cartesian-product row explosion.

#5028 extracted each method's inline `.options(...)` tuple into shared
module-level constants (`_ARTIST_DETAIL_OPTIONS` / `_ARTIST_LIST_OPTIONS`),
so a method's own source no longer contains the `selectinload(`/`joinedload(`
calls directly — it references the constant by name. This now checks the
constants' own source (still selectinload-only) AND that each method
references the correct constant rather than defining its own inline options
(which is exactly the kind of drift #5028 fixed).
"""

import inspect
import re

import pytest

from auralis.library import repositories
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

    def _get_constant_definition_source(self, constant_name: str) -> str:
        """Source text of a module-level `NAME = (...)` assignment.

        Live `Load` objects' `repr()` doesn't name their loader strategy, so
        this reads the constant's own *definition* text instead — same
        approach `_get_source` takes for methods.
        """
        module_src = inspect.getsource(repositories.artist_repository)
        match = re.search(
            rf'^{re.escape(constant_name)}\s*=\s*\((.*?)^\)', module_src,
            re.DOTALL | re.MULTILINE,
        )
        assert match, f"could not find {constant_name}'s definition in artist_repository.py"
        return match.group(0)

    @pytest.mark.parametrize('constant_name', ['_ARTIST_DETAIL_OPTIONS', '_ARTIST_LIST_OPTIONS'])
    def test_shared_eager_load_constants_use_selectinload(self, constant_name):
        """The two constants every read method funnels through (#5028) must
        themselves be selectinload-only — this is where #2613's guarantee
        now actually lives."""
        src = self._get_constant_definition_source(constant_name)
        assert 'selectinload(' in src, f"{constant_name} should use selectinload"
        assert not self._has_joinedload_call(src), f"{constant_name} should not use joinedload"

    def test_get_all_uses_selectinload(self):
        src = self._get_source('get_all')
        assert '_ARTIST_LIST_OPTIONS' in src, "get_all() should use the shared list options constant"
        assert not self._has_joinedload_call(src), "get_all() should not inline its own joinedload"

    def test_get_by_id_uses_selectinload(self):
        src = self._get_source('get_by_id')
        assert '_ARTIST_DETAIL_OPTIONS' in src, "get_by_id() should use the shared detail options constant"
        assert not self._has_joinedload_call(src), "get_by_id() should not inline its own joinedload"

    def test_search_uses_selectinload(self):
        src = self._get_source('search')
        assert '_ARTIST_LIST_OPTIONS' in src, "search() should use the shared list options constant"
        assert not self._has_joinedload_call(src), "search() should not inline its own joinedload"

    def test_get_by_name_uses_selectinload(self):
        src = self._get_source('get_by_name')
        assert '_ARTIST_DETAIL_OPTIONS' in src, "get_by_name() should use the shared detail options constant"
        assert not self._has_joinedload_call(src), "get_by_name() should not inline its own joinedload"
