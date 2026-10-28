"""
K-Nearest Neighbors Graph Builder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Builds and maintains pre-computed similarity graph for fast queries

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from ...library.repositories.similarity_graph_repository import (
    SimilarityGraphRepository,
)
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

    def to_dict(self) -> dict[str, Any]:
        return {
            'total_tracks': self.total_tracks,
            'total_edges': self.total_edges,
            'k_neighbors': self.k_neighbors,
            'avg_distance': self.avg_distance,
            'min_distance': self.min_distance,
            'max_distance': self.max_distance,
            'build_time_seconds': self.build_time_seconds
        }


class GraphBuildInProgress(RuntimeError):
    """A graph build or clear is already running; a second one would corrupt it."""


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
    """

    # Single-flight for build_graph and clear_graph (#5945). A build takes
    # minutes and a closed HTTP request does not cancel it, so a client retry
    # used to start a second build whose edges were inserted on top of the first
    # (duplicates on fresh installs, an IntegrityError mid-way on upgraded ones).
    # Class-level: every builder writes the one similarity_graph table, and a
    # refit may replace the builder instance while a build is still running.
    # Acquired without blocking, so the second caller is told immediately
    # instead of queueing behind a multi-minute build.
    _busy = threading.Lock()

    def __init__(
        self,
        similarity_system: FingerprintSimilarity,
        session_factory: Any,
        graph_repo: SimilarityGraphRepository | None = None,
    ) -> None:
        """
        Initialize graph builder

        Args:
            similarity_system: FingerprintSimilarity instance (already fitted)
            session_factory: SQLAlchemy session factory
            graph_repo: The library's shared repository (``RepositoryFactory.similarity_graph``,
                #5368); built from ``session_factory`` when not supplied
        """
        self.similarity = similarity_system
        self.session_factory = session_factory
        self.graph_repo = graph_repo or SimilarityGraphRepository(session_factory)

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
            clear_existing: Also drop edges of tracks no longer fingerprinted. The
                graph is replaced batch by batch either way, never emptied first

        Returns:
            GraphStats with build statistics
        """
        if not self._busy.acquire(blocking=False):
            raise GraphBuildInProgress("A similarity graph build or clear is already running")
        try:
            return self._build_graph_locked(k, batch_size, clear_existing)
        finally:
            self._busy.release()

    def _build_graph_locked(self, k: int, batch_size: int, clear_existing: bool) -> GraphStats:
        info(f"Building K-NN similarity graph (k={k})...")
        start_time = perf_counter()

        try:
            # Stream fingerprints in batches via keyset pagination to avoid
            # loading the entire fingerprint matrix into RAM (#3454). Keyset
            # (id > last), not OFFSET: a fingerprint inserted or re-versioned
            # while the build runs cannot shift a later page (#5747).
            repo = self.similarity.fingerprint_repo

            batch = repo.get_batch_after_id(0, batch_size)
            if not batch:
                warning("No fingerprints found, cannot build graph")
                return GraphStats(0, 0, k, 0, 0, 0, 0)

            total_edges = 0
            distance_count = 0
            distance_sum = 0.0
            min_distance = float('inf')
            max_distance = float('-inf')
            processed = 0

            while batch:
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
                        distance = float(result.distance)
                        distance_count += 1
                        distance_sum += distance
                        min_distance = min(min_distance, distance)
                        max_distance = max(max_distance, distance)

                # Swap this batch's edges in place: the existing graph is never
                # cleared up front, so readers see no empty graph mid-build (#5747).
                total_edges += self.graph_repo.replace_edges(
                    [fp.track_id for fp in batch], batch_edges_data
                )

                processed += len(batch)
                debug(
                    f"Progress: {processed} tracks processed, "
                    f"{len(batch_edges_data)} edges in batch"
                )
                batch = repo.get_batch_after_id(batch[-1].id, batch_size)

            if clear_existing:
                # Drop edges of tracks that vanished since the previous build.
                self.graph_repo.prune_untracked()

            total_tracks = processed
            info(f"Processed {total_tracks} tracks in batches of {batch_size}")

            # Calculate statistics without retaining O(tracks * k) Python
            # float objects for the duration of the build.
            if distance_count:
                avg_distance = distance_sum / distance_count
            else:
                avg_distance = min_distance = max_distance = 0.0

            build_time = perf_counter() - start_time

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

    def get_neighbors(
        self,
        track_id: int,
        limit: int | None = None
    ) -> list[dict[str, Any]]:
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

    def get_graph_stats(self) -> GraphStats | None:
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
        if not self._busy.acquire(blocking=False):
            raise GraphBuildInProgress("A similarity graph build or clear is already running")
        try:
            count = self.graph_repo.clear_all()
            info(f"Cleared {count} edges from similarity graph")
            return count

        except Exception as e:
            error(f"Failed to clear graph: {e}")
            raise
        finally:
            self._busy.release()
