"""
Similarity Graph Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Data access layer for similarity graph operations

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from sqlalchemy import delete, func, select

from ..models import SimilarityGraph
from .base import BaseRepository


class SimilarityGraphRepository(BaseRepository):
    """Repository for similarity graph database operations"""

    def clear_all(self) -> int:
        """
        Clear all edges from similarity graph

        Returns:
            Number of edges deleted
        """
        with self._session_scope() as session:
            try:
                count = session.execute(select(func.count()).select_from(SimilarityGraph)).scalar_one()
                session.execute(delete(SimilarityGraph))
                session.commit()
                return count
            except Exception:
                session.rollback()
                raise

    def add_edges(self, edges: list[dict[str, Any]]) -> int:
        """
        Add multiple edges to the graph

        Args:
            edges: List of edge dictionaries with keys:
                   track_id, similar_track_id, distance, similarity_score, rank

        Returns:
            Number of edges added
        """
        with self._session_scope() as session:
            try:
                edge_objects = [
                    SimilarityGraph(**edge_data)
                    for edge_data in edges
                ]
                session.add_all(edge_objects)
                session.commit()
                return len(edge_objects)
            except Exception:
                session.rollback()
                raise

    def get_neighbors(
        self,
        track_id: int,
        limit: int | None = None
    ) -> list[SimilarityGraph]:
        """
        Get pre-computed neighbors from graph

        Args:
            track_id: Track ID to get neighbors for
            limit: Maximum number of neighbors (None = all)

        Returns:
            List of SimilarityGraph edges ordered by rank
        """
        with self._session_scope() as session:
            stmt = (
                select(SimilarityGraph)
                .where(SimilarityGraph.track_id == track_id)
                .order_by(SimilarityGraph.rank)
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            edges = list(session.execute(stmt).scalars().all())
            for edge in edges:
                session.expunge(edge)
            return edges

    def get_stats(self) -> tuple[int, int, int, float, float, float] | None:
        """
        Get statistics about the similarity graph

        Returns:
            Tuple of (total_tracks, total_edges, k_neighbors, avg_distance,
                     min_distance, max_distance) or None if graph is empty
        """
        with self._session_scope() as session:
            # Count edges
            total_edges = session.execute(select(func.count()).select_from(SimilarityGraph)).scalar_one()

            if total_edges == 0:
                return None

            # Count unique tracks
            total_tracks = session.execute(
                select(func.count(func.distinct(SimilarityGraph.track_id)))
            ).scalar_one()

            # Calculate k (average neighbors per track)
            k_neighbors = total_edges // total_tracks if total_tracks > 0 else 0

            # Distance statistics
            distance_stats = session.execute(select(
                func.avg(SimilarityGraph.distance),
                func.min(SimilarityGraph.distance),
                func.max(SimilarityGraph.distance)
            )).one()

            avg_distance, min_distance, max_distance = distance_stats

            return (
                total_tracks,
                total_edges,
                k_neighbors,
                float(avg_distance or 0),
                float(min_distance or 0),
                float(max_distance or 0)
            )
