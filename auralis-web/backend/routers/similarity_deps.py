"""
Similarity router dependency plumbing and getters (split from similarity.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.analysis.fingerprint import FingerprintSimilarity, KNNGraphBuilder
from collections.abc import Callable
from typing import Any

from .dependencies import RouterDeps


def _unavailable() -> Any:
    """Placeholder getter used before any router has been built."""
    return None


class _SimilarityDeps:
    """The three callables create_similarity_router() receives."""

    def __init__(
        self,
        get_similarity_system: Callable[[], FingerprintSimilarity] = _unavailable,
        get_graph_builder: Callable[[], KNNGraphBuilder | None] = _unavailable,
        get_repository_factory: Callable[[], Any] = _unavailable,
    ) -> None:
        self.get_similarity_system = get_similarity_system
        self.get_graph_builder = get_graph_builder
        self.get_repository_factory = get_repository_factory


_deps = RouterDeps("similarity", _SimilarityDeps())


def _similarity_system_getter() -> FingerprintSimilarity:
    return _deps.current().get_similarity_system()


def _graph_builder_getter() -> KNNGraphBuilder | None:
    return _deps.current().get_graph_builder()


def _repository_factory_getter() -> Any:
    return _deps.current().get_repository_factory()


def _get_similarity_system_getter() -> Callable[[], FingerprintSimilarity]:
    """Depends() provider handing the handler the live similarity-system getter."""
    return _similarity_system_getter


def _get_graph_builder_getter() -> Callable[[], KNNGraphBuilder | None]:
    """Depends() provider handing the handler the live graph-builder getter."""
    return _graph_builder_getter


def _get_repository_factory_getter() -> Callable[[], Any]:
    """Depends() provider handing the handler the live repository-factory getter."""
    return _repository_factory_getter
