"""
Library router dependency plumbing (split from library.py, #5832).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.thumbnail_cache import artwork_cache_root

from .dependencies import RouterDeps


class _LibraryDeps:
    def __init__(
        self,
        get_repository_factory: Callable[[], Any] = lambda: None,
        resolve_worker: Callable[[str], Any] | None = None,
        get_cache_manager: Callable[[], Any] | None = None,
        get_artwork_cache_dir: Callable[[], Path] = artwork_cache_root,
        get_library_database: Callable[[], Any] | None = None,
    ) -> None:
        self.get_repository_factory = get_repository_factory
        self.resolve_worker = resolve_worker
        self.get_cache_manager = get_cache_manager
        self.get_artwork_cache_dir = get_artwork_cache_dir
        self.get_library_database = get_library_database


_deps = RouterDeps("library", _LibraryDeps())


def _get_deps() -> _LibraryDeps:
    """The collaborators of the router serving this request.

    Handlers resolve the repository factory themselves, at the point the
    original closures did: ``reset_library`` checks its confirmation header
    first, so a bad header is a 400 even when the repositories are down.
    """
    return _deps.current()
