"""
FastAPI Application Configuration

Modular configuration components extracted from monolithic main.py.
Handles app creation, middleware setup, startup events, and router registration.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from typing import Any

__all__ = [
    'create_app',
    'setup_middleware',
    'create_lifespan',
    'setup_routers',
]

# Lazy re-exports (PEP 562). Importing these eagerly pulled in `.routes`, which
# imports the routers — so a leaf import like `from config.limits import ...`
# made from inside a router (#4033) triggered a routers → config → routes →
# routers import cycle when the routers package was imported first. Deferring
# these to attribute-access time breaks that cycle while keeping the public
# `from config import create_app` API intact.
_LAZY = {
    'create_app': ('.app', 'create_app'),
    'setup_middleware': ('.middleware', 'setup_middleware'),
    'setup_routers': ('.routes', 'setup_routers'),
    'create_lifespan': ('.startup', 'create_lifespan'),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module
    module = import_module(target[0], __name__)
    return getattr(module, target[1])
