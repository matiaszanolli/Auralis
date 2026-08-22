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
:license: GPLv3, see LICENSE for more details.
"""

from sqlalchemy import and_, select

from ...utils.logging import error, warning
from ..models import TrackFingerprint
from .base import BaseRepository
from .fingerprint_shared import _current_fingerprint_clause


class FingerprintSimilarityMixin(BaseRepository):
    """Reference-cloud flags/weights and dimension-range pre-filtering."""

    def get_reference_cloud(self) -> list[TrackFingerprint]:
        """Return all fingerprints flagged is_reference=True (schema v15).

        Used by the soft k-NN mastering target derivation to build the
        continuous reference manifold. Indexed via ix_fingerprints_is_reference
        so the lookup is fast even on large libraries.
        """
        with self._session_scope() as session:
            stmt = select(TrackFingerprint).where(TrackFingerprint.is_reference == True)  # noqa: E712
            fingerprints = list(session.execute(stmt).scalars().all())
            for fp in fingerprints:
                session.expunge(fp)
            return fingerprints

    def set_reference_flags(self, track_ids_flagged: dict[int, bool]) -> int:
        """Bulk set is_reference for the given track_ids.

        Used by reference_seeder.refresh_cloud() — clears all existing flags
        then sets the chosen ones in a single transaction so the cloud is
        never partially populated (atomic refresh).

        Args:
            track_ids_flagged: {track_id: True|False} for each track to update.

        Returns:
            Number of rows updated (sum of True + False updates issued).
        """
        if not track_ids_flagged:
            return 0
        # #3681: previous version issued one SELECT + per-row UPDATE per
        # track, producing 2 000 SQLite round-trips for a 2 000-track
        # reference cloud. Two bulk UPDATE statements complete in a single
        # round-trip each. Matches the pattern in `clear_all_reference_flags`.
        from sqlalchemy import update
        flagged_ids = [tid for tid, f in track_ids_flagged.items() if f]
        unflagged_ids = [tid for tid, f in track_ids_flagged.items() if not f]
        session = self.get_session()
        try:
            updated = 0
            if flagged_ids:
                result = session.execute(
                    update(TrackFingerprint)
                    .where(TrackFingerprint.track_id.in_(flagged_ids))
                    .where(TrackFingerprint.is_reference == False)  # noqa: E712
                    .values(is_reference=True)
                )
                updated += result.rowcount or 0
            if unflagged_ids:
                result = session.execute(
                    update(TrackFingerprint)
                    .where(TrackFingerprint.track_id.in_(unflagged_ids))
                    .where(TrackFingerprint.is_reference == True)  # noqa: E712
                    .values(is_reference=False)
                )
                updated += result.rowcount or 0
            session.commit()
            return updated
        finally:
            session.close()

    def set_reference_weights(self, weights: dict[int, float]) -> int:
        """Bulk set reference_weight for the given track_ids (#3480 Layer 1).

        Used by reference_seeder.refresh_cloud() immediately after
        set_reference_flags() flags the selected references — a separate
        call so weight computation (which needs listening-behavior data)
        stays decoupled from the flag-only path other callers may still use.

        Args:
            weights: {track_id: reference_weight} for each reference to update.

        Returns:
            Number of rows updated.
        """
        if not weights:
            return 0
        from sqlalchemy import case, update
        session = self.get_session()
        try:
            result = session.execute(
                update(TrackFingerprint)
                .where(TrackFingerprint.track_id.in_(weights.keys()))
                .values(reference_weight=case(weights, value=TrackFingerprint.track_id))
            )
            session.commit()
            return int(result.rowcount or 0)
        finally:
            session.close()

    def clear_all_reference_flags(self) -> int:
        """Set is_reference=False and reference_weight=0.0 on every fingerprint.

        Returns rows updated.
        """
        from sqlalchemy import update
        session = self.get_session()
        try:
            result = session.execute(
                update(TrackFingerprint)
                .where(TrackFingerprint.is_reference == True)  # noqa: E712
                .values(is_reference=False, reference_weight=0.0)
            )
            session.commit()
            return int(result.rowcount or 0)
        finally:
            session.close()

    def get_by_dimension_range(
        self,
        dimension: str,
        min_value: float,
        max_value: float,
        limit: int | None = None
    ) -> list[TrackFingerprint]:
        """
        Get fingerprints within a specific dimension range

        Useful for pre-filtering before distance calculation

        Args:
            dimension: Name of the dimension (e.g., 'lufs', 'tempo_bpm')
            min_value: Minimum value for the dimension
            max_value: Maximum value for the dimension
            limit: Maximum number of results

        Returns:
            List of TrackFingerprint objects within range
        """
        with self._session_scope() as session:
            # Verify dimension exists
            if not hasattr(TrackFingerprint, dimension):
                error(f"Invalid dimension: {dimension}")
                return []

            dim_attr = getattr(TrackFingerprint, dimension)
            stmt = select(TrackFingerprint).where(
                and_(
                    dim_attr >= min_value,
                    dim_attr <= max_value
                )
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            fingerprints = session.execute(stmt).scalars().all()
            for fp in fingerprints:
                session.expunge(fp)
            return fingerprints

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
            for dimension, (min_val, max_val) in ranges.items():
                if not hasattr(TrackFingerprint, dimension):
                    warning(f"Invalid dimension: {dimension}, skipping")
                    continue

                dim_attr = getattr(TrackFingerprint, dimension)
                conditions.append(and_(
                    dim_attr >= min_val,
                    dim_attr <= max_val
                ))

            if len(conditions) == 1:
                warning("No valid dimension ranges provided")
                return []

            stmt = select(TrackFingerprint).where(and_(*conditions))

            if limit is not None:
                stmt = stmt.limit(limit)

            fingerprints = session.execute(stmt).scalars().all()
            for fp in fingerprints:
                session.expunge(fp)
            return fingerprints
