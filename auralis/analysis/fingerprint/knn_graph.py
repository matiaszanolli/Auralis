# -*- coding: utf-8 -*-

"""
K-Nearest Neighbors Graph Builder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Builds and maintains pre-computed similarity graph for fast queries

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np

from ...utils.logging import debug, error, info, warning
from .similarity import FingerprintSimilarity


@dataclass
class GraphStats:
    """Statistics about the similarity graph"""
    total_tracks: int
    total_edges: int
    k_neighbors: int
    avg_distance: float
    min_distance: float
    max_distance: float
    build_time_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_tracks': self.total_tracks,
            'total_edges': self.total_edges,
            'k_neighbors': self.k_neighbors,
            'avg_distance': self.avg_distance,
            'min_distance': self.min_distance,
            'max_distance': self.max_distance,
            'build_time_seconds': self.build_time_seconds
        }


class KNNGraphBuilder:
    """
    Builds K-nearest neighbors similarity graph

    The graph is stored in the database for fast similarity queries without
    recalculating distances.

    Usage:
        builder = KNNGraphBuilder(
            similarity_system=similarity,
            session_factory=library.SessionLocal
        )

        # Build graph for all tracks
        stats = builder.build_graph(k=10)

        # Update graph for new tracks
        builder.update_graph([new_track_id1, new_track_id2])
    """

    def __init__(
        self,
        similarity_system: FingerprintSimilarity,
        session_factory: Any
    ) -> None:
        """
        Initialize graph builder

        Args:
            similarity_system: FingerprintSimilarity instance (already fitted)
            session_factory: SQLAlchemy session factory
        """
        self.similarity = similarity_system
        self.session_factory = session_factory

        if not self.similarity.is_fitted():
            raise ValueError("Similarity system must be fitted before building graph")

    def build_graph(
        self,
        k: int = 10,
        batch_size: int = 100,
        clear_existing: bool = True
    ) -> GraphStats:
        """
        Build complete K-NN graph for all tracks in library

        Args:
            k: Number of nearest neighbors per track
            batch_size: Number of tracks to process per batch
            clear_existing: Clear existing graph before building

        Returns:
            GraphStats with build statistics
        """
        from ...library.models import SimilarityGraph

        info(f"Building K-NN similarity graph (k={k})...")
        start_time = datetime.now()

        session = self.session_factory()
        try:
            # Clear existing graph if requested
            if clear_existing:
                debug("Clearing existing similarity graph...")
                session.query(SimilarityGraph).delete()
                session.commit()

            # Get all fingerprints
            all_fingerprints = self.similarity.fingerprint_repo.get_all()
            total_tracks = len(all_fingerprints)

            if total_tracks == 0:
                warning("No fingerprints found, cannot build graph")
                return GraphStats(0, 0, k, 0, 0, 0, 0)

            info(f"Processing {total_tracks} tracks in batches of {batch_size}...")

            total_edges = 0
            all_distances = []

            # Process in batches
            for i in range(0, total_tracks, batch_size):
                batch = all_fingerprints[i:i + batch_size]
                batch_edges = 0

                for fp in batch:
                    # Find k nearest neighbors
                    results = self.similarity.find_similar(
                        track_id=fp.track_id,
                        n=k,
                        use_prefilter=True
                    )

                    # Store edges in database
                    for rank, result in enumerate(results, start=1):
                        edge = SimilarityGraph(
                            track_id=fp.track_id,
                            similar_track_id=result.track_id,
                            distance=result.distance,
                            similarity_score=result.similarity_score,
                            rank=rank
                        )
                        session.add(edge)
                        batch_edges += 1
                        all_distances.append(result.distance)

                # Commit batch
                session.commit()
                total_edges += batch_edges

                progress = ((i + len(batch)) / total_tracks) * 100
                debug(f"Progress: {progress:.1f}% ({i + len(batch)}/{total_tracks} tracks, {batch_edges} edges)")

            # Calculate statistics
            if all_distances:
                avg_distance = float(np.mean(all_distances))
                min_distance = float(np.min(all_distances))
                max_distance = float(np.max(all_distances))
            else:
                avg_distance = min_distance = max_distance = 0.0

            build_time = (datetime.now() - start_time).total_seconds()

            stats = GraphStats(
                total_tracks=total_tracks,
                total_edges=total_edges,
                k_neighbors=k,
                avg_distance=avg_distance,
                min_distance=min_distance,
                max_distance=max_distance,
                build_time_seconds=build_time
            )

            info(f"Graph built successfully in {build_time:.1f}s: "
                 f"{total_tracks} tracks, {total_edges} edges")
            debug(f"Distance stats: avg={avg_distance:.4f}, "
                  f"min={min_distance:.4f}, max={max_distance:.4f}")

            return stats

        except Exception as e:
            session.rollback()
            error(f"Failed to build graph: {e}")
            raise
        finally:
            session.close()

    def update_graph(
        self,
        track_ids: List[int],
        k: int = 10
    ) -> int:
        """
        Update graph for specific tracks (e.g., newly added tracks)

        Args:
            track_ids: List of track IDs to update
            k: Number of nearest neighbors

        Returns:
            Number of edges added/updated
        """
        from ...library.models import SimilarityGraph

        info(f"Updating K-NN graph for {len(track_ids)} tracks...")

        session = self.session_factory()
        try:
            edges_updated = 0

            for track_id in track_ids:
                # Remove existing edges for this track
                session.query(SimilarityGraph).filter(
                    SimilarityGraph.track_id == track_id
                ).delete()

                # Find new k nearest neighbors
                results = self.similarity.find_similar(
                    track_id=track_id,
                    n=k,
                    use_prefilter=True
                )

                # Add new edges
                for rank, result in enumerate(results, start=1):
                    edge = SimilarityGraph(
                        track_id=track_id,
                        similar_track_id=result.track_id,
                        distance=result.distance,
                        similarity_score=result.similarity_score,
                        rank=rank
                    )
                    session.add(edge)
                    edges_updated += 1

            session.commit()
            info(f"Updated {edges_updated} edges for {len(track_ids)} tracks")
            return edges_updated

        except Exception as e:
            session.rollback()
            error(f"Failed to update graph: {e}")
            raise
        finally:
            session.close()

    def get_neighbors(
        self,
        track_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get pre-computed neighbors from graph (fast query)

        Args:
            track_id: Track ID to get neighbors for
            limit: Maximum number of neighbors (None = all)

        Returns:
            List of neighbor dictionaries with track_id, distance, similarity_score, rank
        """
        from ...library.models import SimilarityGraph

        session = self.session_factory()
        try:
            query = session.query(SimilarityGraph).filter(
                SimilarityGraph.track_id == track_id
            ).order_by(SimilarityGraph.rank)

            if limit:
                query = query.limit(limit)

            edges = query.all()

            return [edge.to_dict() for edge in edges]

        finally:
            session.close()

    def get_graph_stats(self) -> Optional[GraphStats]:
        """
        Get statistics about current graph

        Returns:
            GraphStats or None if graph is empty
        """
        from sqlalchemy import func

        from ...library.models import SimilarityGraph

        session = self.session_factory()
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

            return GraphStats(
                total_tracks=total_tracks,
                total_edges=total_edges,
                k_neighbors=k_neighbors,
                avg_distance=float(avg_distance or 0),
                min_distance=float(min_distance or 0),
                max_distance=float(max_distance or 0),
                build_time_seconds=0.0  # Not tracked for existing graph
            )

        finally:
            session.close()

    def clear_graph(self) -> int:
        """
        Clear all edges from similarity graph

        Returns:
            Number of edges deleted
        """
        from ...library.models import SimilarityGraph

        session = self.session_factory()
        try:
            count = session.query(SimilarityGraph).count()
            session.query(SimilarityGraph).delete()
            session.commit()

            info(f"Cleared {count} edges from similarity graph")
            return cast(int, count)

        except Exception as e:
            session.rollback()
            error(f"Failed to clear graph: {e}")
            raise
        finally:
            session.close()
