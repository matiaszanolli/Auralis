"""
Files router dependency plumbing (split from files.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from .repo_deps import RepositoryFactoryDeps

_repo_deps = RepositoryFactoryDeps("files")


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
    return _repo_deps.get_repos
