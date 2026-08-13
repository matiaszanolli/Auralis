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
constants' own source AND that each method references the correct constant
rather than defining its own inline options (which is exactly the kind of
drift #5028 fixed).

#5084 made `_ARTIST_LIST_OPTIONS` stronger than "selectinload-only": the list
endpoint's counts now come from `with_expression()` correlated subqueries and
its genre names from one grouped query, so the constant loads *no*
relationship at all. That satisfies #2613's no-Cartesian-product guarantee by
construction, so this file checks the two constants against their respective
contracts rather than holding both to the selectinload rule.
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

    def test_detail_options_use_selectinload(self):
        """`_ARTIST_DETAIL_OPTIONS` genuinely needs the relationships loaded
        (to_dict() walks tracks->genres, tracks->album, albums->tracks), so
        for it #2613's rule still applies verbatim: selectinload, never
        joinedload."""
        src = self._get_constant_definition_source('_ARTIST_DETAIL_OPTIONS')
        assert 'selectinload(' in src, "_ARTIST_DETAIL_OPTIONS should use selectinload"
        assert not self._has_joinedload_call(src), "_ARTIST_DETAIL_OPTIONS should not use joinedload"

    def test_list_options_load_no_relationships(self):
        """`_ARTIST_LIST_OPTIONS` must load no relationship at all (#5084).

        The list endpoint reads only two counts and a genre-name set, which
        now come from `with_expression()` correlated subqueries and one
        grouped query respectively. Reintroducing *either* loader strategy
        here would put full `Track` hydration (including the unbounded
        `lyrics` / `fingerprint_vector` Text columns) back on every page load
        — joinedload as #2613's Cartesian explosion, selectinload as #5084's
        scales-with-tracks-per-artist regression.
        """
        src = self._get_constant_definition_source('_ARTIST_LIST_OPTIONS')
        assert not self._has_joinedload_call(src), "_ARTIST_LIST_OPTIONS should not use joinedload"
        assert 'selectinload(' not in src, (
            "_ARTIST_LIST_OPTIONS should not eager-load relationships — the list "
            "endpoint's counts and genre names come from SQL aggregates (#5084)"
        )
        assert 'with_expression(' in src, (
            "_ARTIST_LIST_OPTIONS should supply the count subqueries via with_expression (#5084)"
        )

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
