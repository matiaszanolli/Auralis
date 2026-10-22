"""
Files router dependency plumbing (split from files.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from .dependencies import RouterDeps, require_repository_factory


class _FilesDeps:
    def __init__(
        self,
        get_repository_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.get_repository_factory = get_repository_factory


_deps = RouterDeps("files", _FilesDeps())


def _get_repos() -> Any:
    """Get repository factory for accessing repositories."""
    return require_repository_factory(_deps.current().get_repository_factory)


def _get_repos_provider() -> Callable[[], Any]:
    """Hand the handler the repository *provider*, not the repositories.

    The original nested handler called get_repos() partway through its body —
    after the empty-batch (400) and file-count (413) checks — so a request
    rejected by either of those never touched the repository factory.
    Resolving the factory through Depends() directly would hoist its 503 ahead
    of both, changing which status an over-large batch gets on a backend with
    no repositories, so the handler keeps calling it itself at the original
    point.
    """
    return _get_repos
