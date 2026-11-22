"""
Component Registry

The process-wide component registry: main.py builds the dict and registers it
here once; readers resolve it at call time through ``get_component_registry()``.
The WebSocket ``ConnectionManager`` lives in ``websocket/connection_manager.py``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

# ---------------------------------------------------------------------------
# Component registry
# ---------------------------------------------------------------------------
#
# #4578: this module used to define its own `globals_dict = create_globals_dict()`
# alongside the one `main.py` builds. Only main.py's was ever populated by
# startup, so anything reading this module's copy saw a permanently-empty
# registry. `_default_get_fingerprints_repository()` did exactly that, which is
# why the #3836 Tier-1 fingerprint fix shipped but never took effect: the key it
# looked up ('repository_factory') was not even declared here.
#
# There is now exactly one registry object in the process. main.py builds it and
# registers it here; readers go through get_component_registry(), which resolves
# at call time — a module-level `globals_dict` would be import-bound and would
# silently re-create the same class of bug for anyone using `from ... import`.

_component_registry: dict[str, Any] | None = None


def set_component_registry(registry: dict[str, Any]) -> None:
    """Register the process-wide component registry (called once, from main.py).

    Startup mutates this same object in place, so readers registered before
    startup completes still observe components as they are populated.
    """
    global _component_registry
    _component_registry = registry


def get_component_registry() -> dict[str, Any] | None:
    """Return the process-wide component registry, or None if unregistered.

    None is the legitimate state in unit tests that never build the app, so
    callers treat it as "component unavailable" rather than an error.
    """
    return _component_registry
