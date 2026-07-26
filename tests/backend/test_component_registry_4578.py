"""One component registry, and Tier-1 fingerprint lookup actually resolves (#4578).

#3836 restored the Tier-1 (database) fingerprint lookup by adding
`_default_get_fingerprints_repository()`, which read
`config.globals.globals_dict`. But the live registry is a *different* dict,
built inline in `main.py` and populated by `config/startup.py`. The dict the
accessor read did not even declare a `repository_factory` key, so it returned
None unconditionally in production and every ChunkedAudioProcessor construction
fell through to the slow fingerprint tiers — the exact cost #3836 was closed to
eliminate. Both the accessor's `except Exception: return None` and the Tier-1
miss log at DEBUG, so nothing surfaced.

The WIRING check that matters here is the last test: a fix that merely *moves*
the key without asserting main.py registers the same object re-creates #3836.
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

import config.globals as globals_mod  # noqa: E402
from core.chunked_processor import _default_get_fingerprints_repository  # noqa: E402


@pytest.fixture
def restore_registry():
    """Preserve/restore the process-wide registry around a test."""
    original = globals_mod.get_component_registry()
    yield
    globals_mod.set_component_registry(original)  # type: ignore[arg-type]


class TestSingleRegistry:

    def test_the_dead_duplicate_registry_is_gone(self):
        """`config.globals` must not define a second, never-populated dict.

        Its existence is what made #3836's fix silently ineffective: it looked
        like a populated registry and `.get()` returned None rather than
        raising.
        """
        assert not hasattr(globals_mod, "globals_dict"), (
            "config.globals.globals_dict is back — a second registry object "
            "re-opens #4578"
        )
        assert not hasattr(globals_mod, "create_globals_dict")

    def test_registry_accessor_round_trips(self, restore_registry):
        registry = {"repository_factory": None}
        globals_mod.set_component_registry(registry)
        assert globals_mod.get_component_registry() is registry

    def test_main_registers_its_own_globals_dict(self):
        """WIRING: the object main.py builds must BE the registered one.

        This is the assertion whose absence let #3836 ship broken.
        """
        import main

        registered = globals_mod.get_component_registry()
        assert registered is not None, "main.py did not register a component registry"
        assert registered is main.globals_dict, (
            "the registered registry is not main.py's globals_dict — startup "
            "populates a different object than readers resolve (#4578)"
        )
        assert registered is main.deps["globals"], (
            "startup receives a different dict than the one registered"
        )

    def test_registry_declares_repository_factory(self):
        """The key the Tier-1 accessor looks up must exist."""
        import main

        assert "repository_factory" in main.globals_dict


class TestTier1Accessor:

    def test_resolves_the_factory_when_startup_has_populated_it(self, restore_registry):
        class _Fingerprints:
            pass

        class _Factory:
            fingerprints = _Fingerprints()

        factory = _Factory()
        # Startup mutates the registered dict in place; model exactly that.
        registry: dict = {"repository_factory": None}
        globals_mod.set_component_registry(registry)
        registry["repository_factory"] = factory

        resolved = _default_get_fingerprints_repository()
        assert resolved is factory.fingerprints, (
            "Tier-1 fingerprint lookup is still dead — mastering targets will "
            "keep falling through to the .25d sidecar and full extraction"
        )

    def test_returns_none_when_no_registry_is_set(self, restore_registry):
        """Bare unit-test context: degrade gracefully, never raise."""
        globals_mod.set_component_registry(None)  # type: ignore[arg-type]
        assert _default_get_fingerprints_repository() is None

    def test_returns_none_before_startup_populates_the_factory(self, restore_registry):
        globals_mod.set_component_registry({"repository_factory": None})
        assert _default_get_fingerprints_repository() is None

    def test_does_not_raise_when_the_factory_is_malformed(self, restore_registry):
        """A genuine failure must still degrade to 'skip Tier 1', not explode."""
        class _Broken:
            @property
            def fingerprints(self):
                raise RuntimeError("repository exploded")

        globals_mod.set_component_registry({"repository_factory": _Broken()})
        assert _default_get_fingerprints_repository() is None
