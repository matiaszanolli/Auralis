"""SimilarityGraphRepository comes from the RepositoryFactory like every other repository (#5368).

KNNGraphBuilder constructed it directly from a raw session factory, the one repository the
factory had no property for. The factory now caches one instance and the builder takes it.
"""

from unittest.mock import MagicMock

from auralis.analysis.fingerprint import KNNGraphBuilder
from auralis.library.repositories import SimilarityGraphRepository


def test_the_factory_exposes_one_cached_similarity_graph_repository(library_database):
    repositories = library_database.repositories

    assert isinstance(repositories.similarity_graph, SimilarityGraphRepository)
    assert repositories.similarity_graph is repositories.similarity_graph


def _fitted_similarity():
    similarity = MagicMock()
    similarity.is_fitted.return_value = True
    return similarity


def test_the_builder_uses_the_repository_it_is_given(library_database):
    shared = library_database.repositories.similarity_graph

    builder = KNNGraphBuilder(_fitted_similarity(), library_database.SessionLocal, graph_repo=shared)

    assert builder.graph_repo is shared


def test_the_builder_still_builds_its_own_when_none_is_given(library_database):
    builder = KNNGraphBuilder(_fitted_similarity(), library_database.SessionLocal)

    assert isinstance(builder.graph_repo, SimilarityGraphRepository)
