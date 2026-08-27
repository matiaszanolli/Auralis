# -*- coding: utf-8 -*-

"""
One registry, one ConnectionManager, and a loud misresolution (#4714)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`config/globals.py` used to end with `globals_dict = create_globals_dict()`,
which ran at import and constructed a second `ConnectionManager` — its own
asyncio.Lock and empty connection list — that no code ever registered a socket
against. The live manager is the one built in `main.py`.

The runtime cost was negligible. The real cost was that this object *looked*
like a populated registry to a reader, and `.get()` on it returned `None`
rather than raising — which is precisely why #3836's Tier-1 fingerprint fix
shipped dead and stayed invisible until #4578.

#4578's consolidation removed the duplicate dict and manager. What it left
behind is the third acceptance criterion of this issue: a misresolved registry
lookup still degraded to `None` in silence. These tests pin all three.
"""

import logging
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

import config.globals as globals_mod  # noqa: E402
from config.globals import ConnectionManager  # noqa: E402
from core.chunked_processor import (  # noqa: E402
    _default_get_fingerprints_repository,
    _reset_registry_miss_warning,
)

_BACKEND = _REPO_ROOT / "auralis-web" / "backend"


@pytest.fixture(autouse=True)
def restore_registry():
    original = globals_mod.get_component_registry()
    _reset_registry_miss_warning()
    yield
    globals_mod.set_component_registry(original)  # type: ignore[arg-type]
    _reset_registry_miss_warning()


class TestNoDuplicateConstruction:
    """Acceptance criteria 1 and 2."""

    def test_globals_module_constructs_nothing_at_import(self):
        """No module-level side-effecting construction unreachable from production."""
        source = (_BACKEND / "config" / "globals.py").read_text()

        # Strip comments: the file documents the removed duplicate by name.
        code = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith("#")
        )
        assert "ConnectionManager()" not in code, (
            "config/globals.py constructs a ConnectionManager at import again — #4714"
        )
        assert "create_globals_dict" not in code

    def test_exactly_one_connection_manager_construction_in_production(self):
        """CONSISTENCY: grep must show exactly one construction site."""
        sites = []
        for path in _BACKEND.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.lstrip()
                if stripped.startswith("#") or stripped.startswith("*"):
                    continue
                if "ConnectionManager()" in line:
                    sites.append(f"{path.relative_to(_BACKEND)}:{lineno}")

        assert sites == ["main.py:104"] or len(sites) == 1, (
            f"expected exactly one ConnectionManager construction, found {sites}"
        )

    def test_the_only_manager_is_the_one_main_built(self):
        """WIRING: every consumer must resolve main.py's single instance.

        The manager is passed through `deps`, not stored in the component
        registry — so the check is that `deps` carries main.manager itself and
        that startup receives that same object.
        """
        import main

        assert isinstance(main.manager, ConnectionManager)
        assert main.deps["manager"] is main.manager

        # And the registry is a *separate* concern that must not sprout its own.
        registry = globals_mod.get_component_registry()
        assert registry is main.globals_dict
        assert not any(
            isinstance(v, ConnectionManager) and v is not main.manager
            for v in registry.values()
        )

    def test_no_test_imports_the_removed_factory(self):
        """WIRING: `grep -rn create_globals_dict tests/` must not find a caller."""
        callers = []
        this_file = Path(__file__).resolve()
        for path in (_REPO_ROOT / "tests").rglob("*.py"):
            # This file names the removed factory in its own prose/assertions.
            if path.resolve() == this_file:
                continue
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if "create_globals_dict" in line and "hasattr" not in line:
                    callers.append(f"{path.relative_to(_REPO_ROOT)}:{lineno}")

        assert callers == [], f"tests still reference the removed factory: {callers}"


class TestMisresolutionIsLoud:
    """Acceptance criterion 3: a misresolved lookup must not degrade silently.

    RETURN VALUE check from the issue: the tolerant path stays tolerant for
    genuine uninitialised cases, and only those.
    """

    def test_registry_missing_the_key_warns(self, caplog):
        """The exact #4578 shape — a dict that does not declare the key — can
        never be main.py's registry, so it means a reader resolved the wrong
        object."""
        globals_mod.set_component_registry({"library_database": None})

        with caplog.at_level(logging.WARNING, logger="core.chunked_processor"):
            assert _default_get_fingerprints_repository() is None

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings, "a misresolved registry must be loud"
        assert "repository_factory" in warnings[0].message

    def test_warning_is_emitted_once_not_per_lookup(self, caplog):
        """The accessor runs per track lookup — an unlatched warning would
        flood the log and get filtered out by whoever reads it."""
        globals_mod.set_component_registry({"library_database": None})

        with caplog.at_level(logging.WARNING, logger="core.chunked_processor"):
            for _ in range(5):
                _default_get_fingerprints_repository()

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1

    def test_broken_factory_warns_instead_of_swallowing(self, caplog):
        """`except Exception: return None` hid genuine failures entirely."""
        class _Broken:
            @property
            def fingerprints(self):
                raise RuntimeError("repository exploded")

        globals_mod.set_component_registry({"repository_factory": _Broken()})

        with caplog.at_level(logging.WARNING, logger="core.chunked_processor"):
            assert _default_get_fingerprints_repository() is None

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings
        assert "repository exploded" in warnings[0].message


class TestLegitimateCasesStayQuiet:
    """The tolerant path must remain tolerant — and silent — where it is right."""

    def test_no_registry_at_all_is_quiet(self, caplog):
        """Bare unit-test context: main.py was never imported."""
        globals_mod.set_component_registry(None)  # type: ignore[arg-type]

        with caplog.at_level(logging.WARNING, logger="core.chunked_processor"):
            assert _default_get_fingerprints_repository() is None

        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_pre_startup_window_is_quiet(self, caplog):
        """The key exists but _init_library_database has not run yet —
        legitimate and transient, not a misresolution."""
        globals_mod.set_component_registry({"repository_factory": None})

        with caplog.at_level(logging.WARNING, logger="core.chunked_processor"):
            assert _default_get_fingerprints_repository() is None

        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_populated_registry_resolves_with_no_warning(self, caplog):
        class _Fingerprints:
            pass

        class _Factory:
            fingerprints = _Fingerprints()

        factory = _Factory()
        globals_mod.set_component_registry({"repository_factory": factory})

        with caplog.at_level(logging.WARNING, logger="core.chunked_processor"):
            assert _default_get_fingerprints_repository() is factory.fingerprints

        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_never_raises_on_any_path(self):
        """Tier-1 is an optimisation; processor construction must not depend on it."""
        for registry in (None, {}, {"repository_factory": None}, {"repository_factory": 1}):
            globals_mod.set_component_registry(registry)  # type: ignore[arg-type]
            _reset_registry_miss_warning()
            _default_get_fingerprints_repository()  # must not raise
