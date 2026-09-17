"""
Regression tests: similarity_graph router success paths (#5491)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every existing test reached only the "no graph_builder" branch, so nothing
pinned ``GraphStatsResponse(**stats.to_dict())`` against the engine's real
``GraphStats`` shape — a field drift on either side would turn every
successful build into a 500. These tests drive the three handlers through a
real FastAPI app with real ``GraphStats`` values.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.analysis.fingerprint.knn_graph import GraphStats, KNNGraphBuilder
from routers.similarity_graph import GraphStatsResponse, create_similarity_graph_router

BUILT = GraphStats(
    total_tracks=12, total_edges=60, k_neighbors=5,
    avg_distance=0.42, min_distance=0.05, max_distance=0.97,
    build_time_seconds=1.25,
)
# What SimilarityGraphRepository.get_stats() returns for a populated graph.
REPO_STATS = (12, 60, 5, 0.42, 0.05, 0.97)


class _FakeBuilder:
    """Stands in for KNNGraphBuilder; stats come from the real conversion."""

    def __init__(self) -> None:
        self.graph_repo = SimpleNamespace(get_stats=lambda: REPO_STATS)
        self.build_calls: list[dict[str, Any]] = []

    def build_graph(self, **kwargs: Any) -> GraphStats:
        self.build_calls.append(kwargs)
        return BUILT

    def get_graph_stats(self) -> GraphStats | None:
        return KNNGraphBuilder.get_graph_stats(self)  # type: ignore[arg-type]

    def clear_graph(self) -> int:
        return 60


@pytest.fixture
def builder() -> _FakeBuilder:
    return _FakeBuilder()


@pytest.fixture
def client(builder: _FakeBuilder) -> TestClient:
    app = FastAPI()
    app.include_router(create_similarity_graph_router(get_graph_builder=lambda: builder))
    return TestClient(app)


def test_response_model_matches_graph_stats_fields():
    engine_fields = {f.name for f in dataclasses.fields(GraphStats)}
    assert set(GraphStatsResponse.model_fields) == engine_fields
    assert set(BUILT.to_dict()) == engine_fields


def test_build_returns_the_built_stats(client, builder):
    response = client.post("/api/similarity/graph/build?k=5&clear_existing=false")

    assert response.status_code == 200
    assert response.json() == BUILT.to_dict()
    assert builder.build_calls == [{"k": 5, "clear_existing": False}]


def test_stats_returns_the_populated_graph(client):
    response = client.get("/api/similarity/graph/stats")

    assert response.status_code == 200
    assert response.json() == {
        "total_tracks": 12, "total_edges": 60, "k_neighbors": 5,
        "avg_distance": 0.42, "min_distance": 0.05, "max_distance": 0.97,
        "build_time_seconds": 0.0,
    }


def test_stats_is_null_for_an_empty_graph(client, builder):
    builder.graph_repo = SimpleNamespace(get_stats=lambda: None)

    response = client.get("/api/similarity/graph/stats")

    assert response.status_code == 200
    assert response.json() is None


def test_clear_reports_deleted_edges(client):
    response = client.delete("/api/similarity/graph")

    assert response.status_code == 200
    assert response.json() == {"edges_deleted": 60}
