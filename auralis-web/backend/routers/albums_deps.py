"""
Albums router dependency plumbing (split from albums.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from fastapi import Depends
from typing import Any

from .dependencies import RouterDeps, require_repository_factory


class _AlbumsDeps:
    def __init__(self, get_repository_factory: Callable[[], Any] = lambda: None) -> None:
        self.get_repository_factory = get_repository_factory


_deps = RouterDeps("albums", _AlbumsDeps())


def _get_repository_factory() -> Callable[[], Any]:
    return _deps.current().get_repository_factory


def _get_repos(
    get_repository_factory: Callable[[], Any] = Depends(_get_repository_factory),
) -> Any:
    """Resolve the RepositoryFactory per request (503 if unavailable).

    Each handler used to open with the identical
    ``repos = require_repository_factory(get_repository_factory)`` line; the
    resolution is still per-request (nothing moved to factory time), it is
    just hoisted into a shared dependency.
    """
    return require_repository_factory(get_repository_factory)
