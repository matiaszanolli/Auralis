"""
Similarity Graph Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Data access layer for similarity graph operations

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...utils.logging import info
from ..models import SimilarityGraph, Track, TrackFingerprint
from .base import BaseRepository
from .fingerprint_shared import _current_fingerprint_clause

# Stay well under SQLite's bound-variable limit for IN (...).
_IN_BATCH = 500

# A track can still be deleted between the liveness check and the INSERT; re-checking that many
# times before giving up covers a scan prune or folder removal that races one batch (#6580).
_DELETED_TRACK_ATTEMPTS = 3


def _edges_between_live_tracks(session: Session, edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The edges both of whose tracks still exist (#6580).

    A K-NN build computes its edges from fingerprints read minutes earlier; a scan prune, a
    scan-folder removal or a track delete in the meantime leaves edges whose similar_track_id is
    gone, and under foreign_keys=ON their INSERT failed the whole batch - and with it the build.
    """
    ids = sorted({e["track_id"] for e in edges} | {e["similar_track_id"] for e in edges})
    live: set[int] = set()
    for start in range(0, len(ids), _IN_BATCH):
        live.update(session.execute(select(Track.id).where(Track.id.in_(ids[start:start + _IN_BATCH]))).scalars())
    kept = [e for e in edges if e["track_id"] in live and e["similar_track_id"] in live]
    if len(kept) < len(edges):
        info(f"Skipped {len(edges) - len(kept)} similarity edge(s) to tracks deleted during the build")
    return kept


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

    def replace_edges(self, track_ids: list[int], edges: list[dict[str, Any]]) -> int:
        """Atomically swap the outgoing edges of ``track_ids`` for ``edges``.

        A rebuild replaces the graph a batch at a time instead of clearing it
        first, so readers keep a usable graph while it is rebuilt (#5747).
        Edges to a track deleted while the build ran are skipped, not fatal (#6580).
        Returns the number of edges added.
        """
        attempts = _DELETED_TRACK_ATTEMPTS
        while True:
            try:
                return self._replace_edges_once(track_ids, edges)
            except IntegrityError:
                # A track went between the liveness check and the INSERT: check again.
                attempts -= 1
                if attempts == 0:
                    raise

    def _replace_edges_once(self, track_ids: list[int], edges: list[dict[str, Any]]) -> int:
        with self._session_scope() as session:
            try:
                for start in range(0, len(track_ids), _IN_BATCH):
                    session.execute(delete(SimilarityGraph).where(
                        SimilarityGraph.track_id.in_(track_ids[start:start + _IN_BATCH])
                    ))
                live = _edges_between_live_tracks(session, edges)
                session.add_all([SimilarityGraph(**edge) for edge in live])
                session.commit()
                return len(live)
            except Exception:
                session.rollback()
                raise

    def prune_untracked(self) -> int:
        """Delete edges whose source track no longer has a current fingerprint.

        The tail of a replace-in-place rebuild: tracks that were deleted or
        went stale since the previous build were never revisited, so their old
        edges would otherwise stay. Returns the number deleted.
        """
        with self._session_scope() as session:
            try:
                current = select(TrackFingerprint.track_id).where(_current_fingerprint_clause())
                result = session.execute(
                    delete(SimilarityGraph).where(SimilarityGraph.track_id.not_in(current))
                )
                session.commit()
                return int(cast(CursorResult[Any], result).rowcount or 0)
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
            Number of edges added (edges to a track that no longer exists are skipped, #6580)
        """
        with self._session_scope() as session:
            try:
                edge_objects = [
                    SimilarityGraph(**edge_data)
                    for edge_data in _edges_between_live_tracks(session, edges)
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
