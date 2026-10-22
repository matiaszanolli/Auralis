"""
Similarity Graph API Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

REST API endpoints for managing the pre-computed K-NN similarity graph
(build / stats / clear). Split out of similarity.py (#4270); all routes keep
their original ``/api/similarity/graph*`` paths.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from auralis.analysis.fingerprint import KNNGraphBuilder

from .dependencies import RouterDeps
from .errors import ServiceUnavailableError
from .similarity_common import _with_similarity_error_handling

logger = logging.getLogger(__name__)


class ClearGraphResponse(BaseModel):
    """Result of clearing the K-NN similarity graph."""
    edges_deleted: int = Field(description="Number of graph edges removed")


class GraphStatsResponse(BaseModel):
    """Similarity graph statistics"""
    total_tracks: int
    total_edges: int
    k_neighbors: int
    avg_distance: float
    min_distance: float
    max_distance: float
    build_time_seconds: float | None = None


class _GraphDeps:
    def __init__(
        self, get_graph_builder: Callable[[], KNNGraphBuilder | None] = lambda: None
    ) -> None:
        self.get_graph_builder = get_graph_builder


_deps = RouterDeps("similarity_graph", _GraphDeps())


def _get_graph_builder() -> KNNGraphBuilder | None:
    """The graph builder for this request; None until the system is fitted."""
    return _deps.current().get_graph_builder()


@_with_similarity_error_handling("Error building graph")
async def build_similarity_graph(
    k: int = Query(10, ge=1, le=50, description="Number of neighbors per track"),
    clear_existing: bool = Query(True, description="Clear existing graph before building"),
    graph_builder: KNNGraphBuilder | None = Depends(_get_graph_builder),
) -> GraphStatsResponse:
    """
    Build K-nearest neighbors similarity graph

    Pre-computes similarity relationships for fast queries.
    This can take several minutes for large libraries.

    Args:
        k: Number of similar tracks to find for each track
        clear_existing: Whether to clear existing graph

    Returns:
        Graph build statistics
    """
    if graph_builder is None:
        raise ServiceUnavailableError("Similarity system not fitted. Please fit the system first using POST /api/similarity/fit")

    # CPU-bound O(N²) K-NN computation; offload to thread so the
    # event loop stays responsive (fixes #2738).
    stats = await asyncio.to_thread(
        graph_builder.build_graph, k=k, clear_existing=clear_existing
    )

    return GraphStatsResponse(**stats.to_dict())


@_with_similarity_error_handling("Error getting graph stats")
async def get_graph_stats(
    graph_builder: KNNGraphBuilder | None = Depends(_get_graph_builder),
) -> GraphStatsResponse | None:
    """
    Get statistics about current similarity graph

    Returns:
        Graph statistics or null if graph not built
    """
    if graph_builder is None:
        return None

    stats = await asyncio.to_thread(graph_builder.get_graph_stats)
    if stats:
        return GraphStatsResponse(**stats.to_dict())
    return None


@_with_similarity_error_handling("Error clearing graph")
async def clear_similarity_graph(
    graph_builder: KNNGraphBuilder | None = Depends(_get_graph_builder),
) -> dict[str, Any]:
    """
    Clear the similarity graph

    Returns:
        Number of edges deleted
    """
    if graph_builder is None:
        return {"edges_deleted": 0}

    count = await asyncio.to_thread(graph_builder.clear_graph)
    return {"edges_deleted": count}


def create_similarity_graph_router(
    get_graph_builder: Callable[[], KNNGraphBuilder | None]
) -> APIRouter:
    """
    Create the similarity-graph management router with dependency injection

    Args:
        get_graph_builder: Callable that returns KNNGraphBuilder instance

    Returns:
        Configured FastAPI router
    """
    deps = _GraphDeps(get_graph_builder)
    router = APIRouter(
        prefix="/api/similarity",
        tags=["similarity-graph"],
        dependencies=[Depends(_deps.bind(deps))],
    )
    router.add_api_route(
        "/graph/build",
        build_similarity_graph,
        methods=["POST"],
        response_model=GraphStatsResponse,
    )
    router.add_api_route(
        "/graph/stats",
        get_graph_stats,
        methods=["GET"],
        response_model=GraphStatsResponse | None,
    )
    router.add_api_route(
        "/graph",
        clear_similarity_graph,
        methods=["DELETE"],
        response_model=ClearGraphResponse,
    )
    return router
