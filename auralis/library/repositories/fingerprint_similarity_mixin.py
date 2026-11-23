"""
Fingerprint Similarity Mixin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Reference-cloud management and dimension-range pre-filtering for
``FingerprintRepository`` — the read/write paths that back similarity search
and the soft k-NN mastering-target derivation (schema v15). Extracted from
fingerprint_repository.py (#4511).

Note: the K-NN graph itself (edges, neighbor queries) lives in
``SimilarityGraphRepository`` — this mixin only supplies the reference-cloud
flags/weights and dimension-range candidate pools that graph building reads
from.

Mixed into ``FingerprintRepository`` alongside ``FingerprintCrudMixin``,
``FingerprintUpsertMixin`` and ``FingerprintQueryMixin`` — same
mixin-composes-BaseRepository layout as ``TrackRepository``'s
``track_repository_*.py`` split (#4511): each mixin inherits
``BaseRepository`` directly for ``get_session``/``_session_scope`` rather
than declaring a bare type annotation for them, so multiple sibling mixins
sharing the same base don't trip mypy's "incompatible definition in base
class" check when composed together on the facade.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, cast

from sqlalchemy import and_, func, select
from sqlalchemy.engine import CursorResult

from ...utils.logging import warning
from ..models import TrackFingerprint
from .base import BaseRepository
from .fingerprint_shared import _FINGERPRINT_WRITABLE_COLS, _current_fingerprint_clause


class FingerprintSimilarityMixin(BaseRepository):
    """Reference-cloud flags/weights and dimension-range pre-filtering."""

    def get_reference_cloud(self) -> list[TrackFingerprint]:
        """Return all fingerprints flagged is_reference=True (schema v15).

        Used by the soft k-NN mastering target derivation to build the
        continuous reference manifold. Indexed via ix_fingerprints_is_reference
        so the lookup is fast even on large libraries.

        Only complete, current-version rows: a stale-version or claim-placeholder
        point would sit in the mastering-target manifold until the next
        refresh_cloud (#5752).
        """
        with self._session_scope() as session:
            stmt = select(TrackFingerprint).where(and_(
                TrackFingerprint.is_reference == True,  # noqa: E712
                _current_fingerprint_clause(),
            ))
            fingerprints = list(session.execute(stmt).scalars().all())
            for fp in fingerprints:
                session.expunge(fp)
            return fingerprints

    def replace_reference_cloud(self, weights: dict[int, float]) -> tuple[int, int]:
        """Make exactly ``weights``' tracks the reference cloud, with those weights, atomically (#6554).

        Used by reference_seeder.refresh_cloud(), which computes the selection
        first. The clear, the flagging and the weights used to be three commits
        around seconds of scoring, so a concurrent get_reference_cloud() could
        read an empty cloud or a flagged-but-unweighted one, and two overlapping
        refreshes left the union of both selections flagged. Here they are one
        transaction, write-locked from its first UPDATE: readers see the old
        cloud or the new one, and overlapping refreshes serialise, the later
        selection winning whole. Track ids without a fingerprint row are ignored.

        Returns:
            (previously flagged rows cleared, rows now flagged).
        """
        from sqlalchemy import case, update
        with self._session_scope() as session:
            result = session.execute(
                update(TrackFingerprint)
                .where(TrackFingerprint.is_reference == True)  # noqa: E712
                .values(is_reference=False, reference_weight=0.0)
            )
            cleared = int(cast(CursorResult[Any], result).rowcount or 0)
            flagged = 0
            if weights:
                result = session.execute(
                    update(TrackFingerprint)
                    .where(TrackFingerprint.track_id.in_(weights.keys()))
                    .values(
                        is_reference=True,
                        reference_weight=case(weights, value=TrackFingerprint.track_id),
                    )
                )
                flagged = int(cast(CursorResult[Any], result).rowcount or 0)
            session.commit()
            return cleared, flagged

    def get_by_multi_dimension_range(
        self,
        ranges: dict[str, tuple[float, float]],
        limit: int | None = None
    ) -> list[TrackFingerprint]:
        """
        Get fingerprints within multiple dimension ranges

        More efficient pre-filtering for similarity search. Excludes
        in-progress claim placeholders and stale-algorithm-version rows
        (#4822), same as every other read on this repository.

        Rows come back closest-first: ordered by the L1 distance from the
        centre of the box, each dimension scaled by its half-width so a
        +/-15 BPM tolerance and a +/-0.08 bass fraction weigh the same, with
        ``track_id`` as the tie-break. Without an ORDER BY, ``limit`` kept the
        lowest rowids -- the oldest fingerprints -- and dropped the true
        nearest neighbours of any box holding more than ``limit`` rows (#5715).

        Args:
            ranges: Dictionary mapping dimension names to (min, max) tuples
                   e.g., {'lufs': (-20, -10), 'tempo_bpm': (100, 140)}
            limit: Maximum number of results

        Returns:
            List of TrackFingerprint objects matching all range criteria
        """
        with self._session_scope() as session:
            # Build filter conditions
            conditions = [_current_fingerprint_clause()]
            distance_terms = []
            for dimension, (min_val, max_val) in ranges.items():
                # Column names only: hasattr() also accepted relationships and methods.
                if dimension not in _FINGERPRINT_WRITABLE_COLS:
                    warning(f"Invalid dimension: {dimension}, skipping")
                    continue

                dim_attr = getattr(TrackFingerprint, dimension)
                conditions.append(and_(
                    dim_attr >= min_val,
                    dim_attr <= max_val
                ))
                half_width = (max_val - min_val) / 2.0
                if half_width > 0:
                    distance_terms.append(
                        func.abs(dim_attr - (min_val + max_val) / 2.0) / half_width
                    )

            if len(conditions) == 1:
                warning("No valid dimension ranges provided")
                return []

            stmt = select(TrackFingerprint).where(and_(*conditions))

            if distance_terms:
                stmt = stmt.order_by(sum(distance_terms[1:], distance_terms[0]))
            stmt = stmt.order_by(TrackFingerprint.track_id)

            if limit is not None:
                stmt = stmt.limit(limit)

            fingerprints = list(session.execute(stmt).scalars().all())
            for fp in fingerprints:
                session.expunge(fp)
            return fingerprints
