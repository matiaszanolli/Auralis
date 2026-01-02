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

from ...library.repositories.similarity_graph_repository import SimilarityGraphRepository
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
        self.graph_repo = SimilarityGraphRepository(session_factory)

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
        info(f"Building K-NN similarity graph (k={k})...")
        start_time = datetime.now()

        try:
            # Clear existing graph if requested
            if clear_existing:
                debug("Clearing existing similarity graph...")
                self.graph_repo.clear_all()

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
                batch_edges_data = []

                for fp in batch:
                    # Find k nearest neighbors
                    results = self.similarity.find_similar(
                        track_id=fp.track_id,
                        n=k,
                        use_prefilter=True
                    )

                    # Prepare edges for batch insertion
                    for rank, result in enumerate(results, start=1):
                        edge_data = {
                            'track_id': fp.track_id,
                            'similar_track_id': result.track_id,
                            'distance': result.distance,
                            'similarity_score': result.similarity_score,
                            'rank': rank
                        }
                        batch_edges_data.append(edge_data)
                        all_distances.append(result.distance)

                # Add batch of edges to database
                if batch_edges_data:
                    batch_edges = self.graph_repo.add_edges(batch_edges_data)
                    total_edges += batch_edges

                progress = ((i + len(batch)) / total_tracks) * 100
                debug(f"Progress: {progress:.1f}% ({i + len(batch)}/{total_tracks} tracks, {len(batch_edges_data)} edges)")

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
            error(f"Failed to build graph: {e}")
            raise

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
        info(f"Updating K-NN graph for {len(track_ids)} tracks...")

        try:
            edges_updated = 0

            for track_id in track_ids:
                # Remove existing edges for this track
                self.graph_repo.delete_by_track_id(track_id)

                # Find new k nearest neighbors
                results = self.similarity.find_similar(
                    track_id=track_id,
                    n=k,
                    use_prefilter=True
                )

                # Prepare new edges
                edge_data_list = []
                for rank, result in enumerate(results, start=1):
                    edge_data = {
                        'track_id': track_id,
                        'similar_track_id': result.track_id,
                        'distance': result.distance,
                        'similarity_score': result.similarity_score,
                        'rank': rank
                    }
                    edge_data_list.append(edge_data)

                # Add new edges
                if edge_data_list:
                    edges_updated += self.graph_repo.add_edges(edge_data_list)

            info(f"Updated {edges_updated} edges for {len(track_ids)} tracks")
            return edges_updated

        except Exception as e:
            error(f"Failed to update graph: {e}")
            raise

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
        edges = self.graph_repo.get_neighbors(track_id, limit)
        return [edge.to_dict() for edge in edges]

    def get_graph_stats(self) -> Optional[GraphStats]:
        """
        Get statistics about current graph

        Returns:
            GraphStats or None if graph is empty
        """
        stats = self.graph_repo.get_stats()

        if stats is None:
            return None

        total_tracks, total_edges, k_neighbors, avg_distance, min_distance, max_distance = stats

        return GraphStats(
            total_tracks=total_tracks,
            total_edges=total_edges,
            k_neighbors=k_neighbors,
            avg_distance=avg_distance,
            min_distance=min_distance,
            max_distance=max_distance,
            build_time_seconds=0.0  # Not tracked for existing graph
        )

    def clear_graph(self) -> int:
        """
        Clear all edges from similarity graph

        Returns:
            Number of edges deleted
        """
        try:
            count = self.graph_repo.clear_all()
            info(f"Cleared {count} edges from similarity graph")
            return cast(int, count)

        except Exception as e:
            error(f"Failed to clear graph: {e}")
            raise
