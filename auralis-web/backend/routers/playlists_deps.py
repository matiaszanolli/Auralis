"""
Playlists router dependency plumbing (split from playlists.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from .dependencies import RouterDeps
from .repo_deps import RepositoryFactoryDeps


class _PlaylistsDeps:
    def __init__(self, connection_manager: Any = None) -> None:
        self.connection_manager = connection_manager


_repo_deps = RepositoryFactoryDeps("playlists")
_deps = RouterDeps("playlists", _PlaylistsDeps())


def _get_connection_manager() -> Any:
    return _deps.current().connection_manager
