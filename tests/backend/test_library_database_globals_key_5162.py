# -*- coding: utf-8 -*-

"""
The globals key names its own type: `library_database` (#5162)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`LibraryManager` was deleted in #4915, but the composition root went on storing
the `LibraryDatabase` instance under a key named after the deleted class for a
month — 129 references across 32 non-test files, the single largest source of
false grep leads in the backend.

The rename is guarded here rather than by mypy, which cannot see it at all: the
globals dict is string-keyed, so a site missed by the rename raises `KeyError`
(or silently reads `None`) at request time, not at type-check time. These tests
pin both halves of the contract — the writer stores under the new key, and the
readers look it up there.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import main  # noqa: E402
from config import routes as routes_mod  # noqa: E402


class TestGlobalsKey:
    def test_the_globals_dict_declares_the_new_key_only(self):
        assert "library_database" in main.globals_dict
        assert "library_manager" not in main.globals_dict, (
            "the key still names LibraryManager, deleted in #4915"
        )

    def test_routes_wire_the_routers_to_the_new_key(self):
        """routes.py builds `get_component(key)` closures over the key string.

        That string is the one place a rename typo survives every static tool,
        so assert the real wiring rather than a reconstructed closure.
        """
        source = Path(routes_mod.__file__).read_text()

        assert "get_component('library_database')" in source, (
            "routes.py no longer resolves the library database by its new key"
        )
        assert "library_manager" not in source

    def test_startup_declares_the_key_before_anything_populates_it(self):
        """main.py seeds every component key with None so a router asking for
        one before startup gets a 503 rather than a KeyError."""
        source = Path(main.__file__).read_text()

        assert "'library_database': None" in source
        assert "library_manager" not in source


class TestNoStaleReferences:
    """The acceptance criterion, as an executable check rather than a one-off
    grep in a closed issue."""

    _ROOTS = ("auralis", "auralis-web/backend")

    def _sources(self):
        repo = Path(__file__).parent.parent.parent
        for root in self._ROOTS:
            for path in (repo / root).rglob("*.py"):
                parts = path.parts
                if any(p in ("tests", "test") for p in parts):
                    continue
                if path.name.startswith("test_"):
                    continue
                yield path

    def test_no_production_file_still_says_library_manager(self):
        offenders = [
            f"{path}:{i}"
            for path in self._sources()
            for i, line in enumerate(path.read_text().splitlines(), 1)
            if "library_manager" in line
        ]
        assert offenders == [], (
            "library_manager survives in production code: " + ", ".join(offenders)
        )

    def test_the_live_exception_keeps_its_name(self):
        """`LibraryManagerUnavailableError` is a real, raised exception — not
        part of the retired class — and must NOT be swept up by the rename."""
        from routers.errors import LibraryManagerUnavailableError

        assert LibraryManagerUnavailableError.__name__ == "LibraryManagerUnavailableError"
        assert issubclass(LibraryManagerUnavailableError, Exception)
