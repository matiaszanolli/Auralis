# -*- coding: utf-8 -*-

"""
Similarity Graph Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Data access layer for similarity graph operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import SimilarityGraph


class SimilarityGraphRepository:
    """Repository for similarity graph database operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get_session(self) -> Session:
        return self.session_factory()

    def clear_all(self) -> int:
        """
        Clear all edges from similarity graph

        Returns:
            Number of edges deleted
        """
        session = self.get_session()
        try:
            count = session.query(SimilarityGraph).count()
            session.query(SimilarityGraph).delete()
            session.commit()
            return count
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_by_track_id(self, track_id: int) -> int:
        """
        Delete all edges for a specific track

        Args:
            track_id: Track ID to delete edges for

        Returns:
            Number of edges deleted
        """
        session = self.get_session()
        try:
            count = (
                session.query(SimilarityGraph)
                .filter(SimilarityGraph.track_id == track_id)
                .count()
            )
            session.query(SimilarityGraph).filter(
                SimilarityGraph.track_id == track_id
            ).delete()
            session.commit()
            return count
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def add_edges(self, edges: List[Dict[str, Any]]) -> int:
        """
        Add multiple edges to the graph

        Args:
            edges: List of edge dictionaries with keys:
                   track_id, similar_track_id, distance, similarity_score, rank

        Returns:
            Number of edges added
        """
        session = self.get_session()
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
        finally:
            session.close()

    def add_edge(
        self,
        track_id: int,
        similar_track_id: int,
        distance: float,
        similarity_score: float,
        rank: int
    ) -> None:
        """
        Add a single edge to the graph

        Args:
            track_id: Source track ID
            similar_track_id: Target similar track ID
            distance: Distance metric
            similarity_score: Similarity score (0-1)
            rank: Rank of this neighbor (1 = closest)
        """
        session = self.get_session()
        try:
            edge = SimilarityGraph(
                track_id=track_id,
                similar_track_id=similar_track_id,
                distance=distance,
                similarity_score=similarity_score,
                rank=rank
            )
            session.add(edge)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_neighbors(
        self,
        track_id: int,
        limit: Optional[int] = None
    ) -> List[SimilarityGraph]:
        """
        Get pre-computed neighbors from graph

        Args:
            track_id: Track ID to get neighbors for
            limit: Maximum number of neighbors (None = all)

        Returns:
            List of SimilarityGraph edges ordered by rank
        """
        session = self.get_session()
        try:
            query = (
                session.query(SimilarityGraph)
                .filter(SimilarityGraph.track_id == track_id)
                .order_by(SimilarityGraph.rank)
            )

            if limit:
                query = query.limit(limit)

            return query.all()
        finally:
            session.close()

    def get_stats(self) -> Optional[Tuple[int, int, int, float, float, float]]:
        """
        Get statistics about the similarity graph

        Returns:
            Tuple of (total_tracks, total_edges, k_neighbors, avg_distance,
                     min_distance, max_distance) or None if graph is empty
        """
        session = self.get_session()
        try:
            # Count edges
            total_edges = session.query(SimilarityGraph).count()

            if total_edges == 0:
                return None

            # Count unique tracks
            total_tracks = session.query(
                func.count(func.distinct(SimilarityGraph.track_id))
            ).scalar()

            # Calculate k (average neighbors per track)
            k_neighbors = total_edges // total_tracks if total_tracks > 0 else 0

            # Distance statistics
            distance_stats = session.query(
                func.avg(SimilarityGraph.distance),
                func.min(SimilarityGraph.distance),
                func.max(SimilarityGraph.distance)
            ).first()

            avg_distance, min_distance, max_distance = distance_stats

            return (
                total_tracks,
                total_edges,
                k_neighbors,
                float(avg_distance or 0),
                float(min_distance or 0),
                float(max_distance or 0)
            )
        finally:
            session.close()

    def count_edges(self) -> int:
        """
        Count total number of edges in graph

        Returns:
            Total edge count
        """
        session = self.get_session()
        try:
            return session.query(SimilarityGraph).count()
        finally:
            session.close()
