"""
Per-router injection of the one dependency many routers share: the
repository-factory getter (#5832).

Routers whose only collaborator is ``get_repository_factory`` would otherwise
each carry the same ten-line ``RouterDeps`` holder. One ``RepositoryFactoryDeps``
per router module replaces it::

    _repo_deps = RepositoryFactoryDeps("tracks")

    async def get_track(repos: Any = Depends(_repo_deps.get_repos)): ...

    def create_tracks_router(get_repository_factory):
        router = APIRouter(dependencies=[Depends(_repo_deps.bind(get_repository_factory))])

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Awaitable, Callable
from typing import Any

from .dependencies import RouterDeps, require_repository_factory


class _FactoryGetter:
    def __init__(self, get_repository_factory: Callable[[], Any] | None = None) -> None:
        self.get_repository_factory = get_repository_factory


class RepositoryFactoryDeps:
    """One router module's repository-factory getter, isolated per router instance."""

    def __init__(self, name: str) -> None:
        self._deps = RouterDeps(name, _FactoryGetter())

    def bind(self, get_repository_factory: Callable[[], Any] | None) -> Callable[[], Awaitable[None]]:
        """The router-level dependency publishing this factory call's getter."""
        return self._deps.bind(_FactoryGetter(get_repository_factory))

    def get_repos(self) -> Any:
        """Resolve the RepositoryFactory per request (503 if unavailable)."""
        return require_repository_factory(self._deps.current().get_repository_factory)
