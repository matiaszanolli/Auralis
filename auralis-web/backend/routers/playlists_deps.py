"""
Playlists router dependency plumbing (split from playlists.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from .dependencies import RouterDeps, require_repository_factory


class _PlaylistsDeps:
    def __init__(
        self,
        get_repository_factory: Callable[[], Any] = lambda: None,
        connection_manager: Any = None,
    ) -> None:
        self.get_repository_factory = get_repository_factory
        self.connection_manager = connection_manager


_deps = RouterDeps("playlists", _PlaylistsDeps())


def _get_connection_manager() -> Any:
    return _deps.current().connection_manager


def _get_repos() -> Any:
    """Resolve the RepositoryFactory for this request.

    Mirrors the original per-handler `require_repository_factory(
    get_repository_factory)` call exactly: the factory getter is invoked (and
    its 503-on-unavailable guard applied) once per request, not once at
    router-construction time.
    """
    return require_repository_factory(_deps.current().get_repository_factory)
