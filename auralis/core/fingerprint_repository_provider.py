"""
Where the engine finds the fingerprint repository (#5722)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ContinuousMode`` needs the library's fingerprint repository to derive the reference-cloud target
EQ. The engine used to reach it by importing the backend's top-level ``config.globals`` module,
which resolves only when ``auralis-web/backend`` happens to be on ``sys.path`` and otherwise
silently degraded to "no repository". The application registers a provider here at startup
instead; with none registered (a bare engine, a unit test) the engine runs on the legacy
deficit-based EQ, as before.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from ..utils.logging import debug

_provider: Callable[[], Any | None] | None = None


def set_fingerprint_repository_provider(provider: Callable[[], Any | None] | None) -> None:
    """Register (or, with None, clear) the callable that returns the fingerprint repository."""
    global _provider
    _provider = provider


def get_fingerprint_repository() -> Any | None:
    """The registered repository, or None when none is registered or the provider fails."""
    if _provider is None:
        return None
    try:
        return _provider()
    except Exception as e:
        debug(f"Fingerprint repository unavailable for ContinuousMode: {e}")
        return None
