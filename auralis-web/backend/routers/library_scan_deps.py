"""
Library-scan router dependency plumbing (split from library_scan.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from .dependencies import RouterDeps


class _LibraryScanDeps:
    def __init__(
        self,
        get_library_database: Callable[[], Any] | None = None,
        connection_manager: Any = None,
    ) -> None:
        self.get_library_database = get_library_database
        self.connection_manager = connection_manager


_deps = RouterDeps("library_scan", _LibraryScanDeps())


def _get_library_database() -> Any:
    """Resolve the LibraryDatabase, or None when the app has none.

    Resolving here (rather than in each handler) keeps the #4656 guard
    meaningful: handlers check the *resolved* manager for None, which the
    always-truthy getter callable could never expose.
    """
    getter = _deps.current().get_library_database
    return getter() if getter else None


def _get_connection_manager() -> Any:
    return _deps.current().connection_manager
