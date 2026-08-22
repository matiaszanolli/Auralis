"""
A graph narrower than the request must not silently under-serve it — #4864
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`KNNGraphBuilder.build_graph(k=...)` stores a fixed number of edges per track.
`get_neighbors(track_id, limit=N)` caps that stored list at `N` but cannot extend
it, so `GET /tracks/{id}/similar?limit=50` against a graph built with `k=10`
returned 10 results — with nothing distinguishing "the library only has 10
similar tracks" from "the graph was not built wide enough".

The router only fell back to the real-time search when the neighbour list was
*empty*. It now falls back whenever the list is *shorter than requested*, which
is the same condition: the graph cannot answer this question.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


def _edge(rank: int) -> dict[str, float | int]:
    """One stored graph edge, shaped as `get_neighbors` returns it."""
    return {
        "similar_track_id": 1000 + rank,
        "distance": 0.01 * rank,
        "similarity_score": 1.0 - 0.01 * rank,
        "rank": rank,
    }


def _realtime(track_id: int) -> Mock:
    """One `SimilarityResult` from the real-time search."""
    result = Mock()
    result.track_id = track_id
    result.distance = 0.5
    result.similarity_score = 0.5
    return result


def _handler(graph_builder: Mock, similarity: Mock):
    """Build the router against mocks and return the /similar endpoint."""
    from routers.similarity import create_similarity_router

    router = create_similarity_router(
        get_similarity_system=lambda: similarity,
        get_graph_builder=lambda: graph_builder,
        get_repository_factory=lambda: Mock(),
    )
    for route in router.routes:
        if getattr(route, "path", None) == "/api/similarity/tracks/{track_id}/similar":
            return route.endpoint
    raise AssertionError("Could not find the /similar endpoint")


@pytest.fixture
def similarity() -> Mock:
    system = Mock()
    system.is_fitted.return_value = True
    system.find_similar.return_value = [_realtime(2000 + i) for i in range(50)]
    return system


@pytest.fixture
def graph_builder() -> Mock:
    return Mock()


async def _call(graph_builder: Mock, similarity: Mock, limit: int):
    """Invoke the endpoint with the preconditions and detail lookup stubbed."""
    handler = _handler(graph_builder, similarity)
    with patch("routers.similarity.require_repository_factory", return_value=Mock()), \
         patch("routers.similarity.require_fingerprinted_tracks", new_callable=AsyncMock):
        return await handler(
            track_id=1, limit=limit, use_graph=True, include_details=False
        )


class TestGraphNarrowerThanRequest:
    @pytest.mark.asyncio
    async def test_falls_back_when_the_graph_holds_fewer_than_requested(
        self, graph_builder, similarity
    ):
        """The regression: k=10 graph, limit=50 request."""
        graph_builder.get_neighbors.return_value = [_edge(i) for i in range(1, 11)]

        results = await _call(graph_builder, similarity, limit=50)

        # Pre-fix: 10 results straight off the graph, no real-time search.
        similarity.find_similar.assert_called_once()
        assert len(results) == 50

    @pytest.mark.asyncio
    async def test_the_results_come_from_the_real_time_search(
        self, graph_builder, similarity
    ):
        """Not a merge of two rankings — one coherent source."""
        graph_builder.get_neighbors.return_value = [_edge(i) for i in range(1, 11)]

        results = await _call(graph_builder, similarity, limit=50)

        assert all(r.track_id >= 2000 for r in results), "graph ids leaked in"
        assert [r.rank for r in results] == list(range(1, 51))

    @pytest.mark.asyncio
    async def test_one_short_is_enough_to_fall_back(self, graph_builder, similarity):
        """The boundary: `len(neighbors) == limit - 1`."""
        graph_builder.get_neighbors.return_value = [_edge(i) for i in range(1, 10)]

        await _call(graph_builder, similarity, limit=10)

        similarity.find_similar.assert_called_once()


class TestFastPathPreserved:
    @pytest.mark.asyncio
    async def test_an_exactly_wide_enough_graph_is_used_as_is(
        self, graph_builder, similarity
    ):
        """The common case — router and builder share a default of 10."""
        graph_builder.get_neighbors.return_value = [_edge(i) for i in range(1, 11)]

        results = await _call(graph_builder, similarity, limit=10)

        similarity.find_similar.assert_not_called()
        assert len(results) == 10
        assert all(r.track_id >= 1000 for r in results)

    @pytest.mark.asyncio
    async def test_a_wider_graph_than_needed_is_still_used(
        self, graph_builder, similarity
    ):
        """`get_neighbors` already caps at `limit`, so this is the >= case."""
        graph_builder.get_neighbors.return_value = [_edge(i) for i in range(1, 6)]

        results = await _call(graph_builder, similarity, limit=5)

        similarity.find_similar.assert_not_called()
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_the_graph_is_asked_for_exactly_the_requested_limit(
        self, graph_builder, similarity
    ):
        graph_builder.get_neighbors.return_value = [_edge(i) for i in range(1, 11)]

        await _call(graph_builder, similarity, limit=10)

        assert graph_builder.get_neighbors.call_args.kwargs["limit"] == 10


class TestExistingBehaviourUnchanged:
    @pytest.mark.asyncio
    async def test_an_empty_graph_still_falls_back(self, graph_builder, similarity):
        """The case that already worked — it is now one branch, not two."""
        graph_builder.get_neighbors.return_value = []

        await _call(graph_builder, similarity, limit=10)

        similarity.find_similar.assert_called_once()

    @pytest.mark.asyncio
    async def test_a_genuinely_small_library_returns_what_it_has(
        self, graph_builder, similarity
    ):
        """Falling back cannot invent tracks; it returns the same short list.

        This is the cost of the fix — a redundant search when the library really
        does hold fewer than `limit` similar tracks — and the point is that it is
        still correct, just not free.
        """
        graph_builder.get_neighbors.return_value = [_edge(1), _edge(2)]
        similarity.find_similar.return_value = [_realtime(2000), _realtime(2001)]

        results = await _call(graph_builder, similarity, limit=50)

        similarity.find_similar.assert_called_once()
        assert len(results) == 2
