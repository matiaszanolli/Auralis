"""
Fingerprint Repository
~~~~~~~~~~~~~~~~~~~~~

Data access layer for track fingerprint operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any
from collections.abc import Callable

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from ...utils.logging import debug, error, info, warning
from ...__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..fingerprint_quantizer import FingerprintQuantizer
from ..models import Track, TrackFingerprint

# Whitelist of columns callers may supply to upsert() / store_fingerprint().
# Derived from the SQLAlchemy model so it stays in sync automatically (#2286).
# Excludes auto-managed columns (PK, timestamps) that callers must never set.
_FINGERPRINT_WRITABLE_COLS: frozenset[str] = (
    frozenset(TrackFingerprint.__table__.columns.keys())
    - {'id', 'created_at', 'updated_at'}
)


def _validate_fingerprint_columns(cols: list[str]) -> None:
    """Raise ValueError if any column name is not in the allowed whitelist.

    Prevents SQL injection via f-string column interpolation (#2286).

    Args:
        cols: Column names to validate before interpolation into SQL

    Raises:
        ValueError: If any column is not in _FINGERPRINT_WRITABLE_COLS
    """
    bad = set(cols) - _FINGERPRINT_WRITABLE_COLS
    if bad:
        raise ValueError(
            f"Invalid fingerprint column name(s): {sorted(bad)}. "
            f"Allowed: {sorted(_FINGERPRINT_WRITABLE_COLS)}"
        )


class FingerprintRepository:
    """Repository for fingerprint database operations"""

    def __init__(
        self,
        session_factory: Callable[[], Session],
    ) -> None:
        """
        Initialize fingerprint repository

        Args:
            session_factory: SQLAlchemy session factory used for all DB access.
        """
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def add(self, track_id: int, fingerprint_data: dict[str, float]) -> TrackFingerprint | None:
        """
        Add a fingerprint for a track

        Args:
            track_id: ID of the track
            fingerprint_data: Dictionary with all 25 fingerprint dimensions

        Returns:
            TrackFingerprint object if successful, None if failed
        """
        session = self.get_session()
        try:
            # Check if fingerprint already exists
            existing = session.execute(
                select(TrackFingerprint).where(TrackFingerprint.track_id == track_id)
            ).scalars().first()

            if existing:
                debug(f"Fingerprint already exists for track {track_id}, updating")
                return self.update(track_id, fingerprint_data)

            # Create new fingerprint
            fingerprint = TrackFingerprint(
                track_id=track_id,
                **fingerprint_data
            )

            session.add(fingerprint)
            session.commit()
            session.refresh(fingerprint)

            # CRITICAL: Detach object from session before returning
            session.expunge(fingerprint)

            info(f"Added fingerprint for track {track_id}")
            return fingerprint

        except Exception as e:
            session.rollback()
            error(f"Failed to add fingerprint for track {track_id}: {e}")
            return None
        finally:
            # CRITICAL: Explicitly clear session to free memory
            session.expunge_all()
            session.close()

    def get_by_track_ids(self, track_ids: list[int]) -> list[TrackFingerprint]:
        """
        Get fingerprints for multiple tracks in a single query.

        Args:
            track_ids: List of track IDs

        Returns:
            List of TrackFingerprint objects (only for tracks that have fingerprints)
        """
        if not track_ids:
            return []
        session = self.get_session()
        try:
            fingerprints = session.execute(
                select(TrackFingerprint).where(TrackFingerprint.track_id.in_(track_ids))
            ).scalars().all()
            for fp in fingerprints:
                session.expunge(fp)
            return list(fingerprints)
        finally:
            session.close()

    def get_by_track_id(self, track_id: int) -> TrackFingerprint | None:
        """
        Get fingerprint by track ID

        Args:
            track_id: ID of the track

        Returns:
            TrackFingerprint object if found, None otherwise
        """
        session = self.get_session()
        try:
            fingerprint = session.execute(
                select(TrackFingerprint).where(TrackFingerprint.track_id == track_id)
            ).scalars().first()
            if fingerprint:
                session.expunge(fingerprint)
            return fingerprint
        finally:
            session.close()

    def update(self, track_id: int, fingerprint_data: dict[str, float]) -> TrackFingerprint | None:
        """
        Update an existing fingerprint

        Args:
            track_id: ID of the track
            fingerprint_data: Dictionary with fingerprint dimensions to update

        Returns:
            Updated TrackFingerprint object if successful, None if failed
        """
        session = self.get_session()
        try:
            fingerprint = session.execute(
                select(TrackFingerprint).where(TrackFingerprint.track_id == track_id)
            ).scalars().first()

            if not fingerprint:
                warning(f"Fingerprint not found for track {track_id}")
                return None

            # Update all provided fields
            for key, value in fingerprint_data.items():
                if hasattr(fingerprint, key):
                    setattr(fingerprint, key, value)

            session.commit()
            session.refresh(fingerprint)

            # CRITICAL: Detach object from session before returning
            session.expunge(fingerprint)

            info(f"Updated fingerprint for track {track_id}")
            return fingerprint

        except Exception as e:
            session.rollback()
            error(f"Failed to update fingerprint for track {track_id}: {e}")
            return None
        finally:
            # CRITICAL: Explicitly clear session to free memory
            session.expunge_all()
            session.close()

    def delete(self, track_id: int) -> bool:
        """
        Delete a fingerprint

        Args:
            track_id: ID of the track

        Returns:
            True if successful, False otherwise
        """
        session = self.get_session()
        try:
            fingerprint = session.execute(
                select(TrackFingerprint).where(TrackFingerprint.track_id == track_id)
            ).scalars().first()

            if not fingerprint:
                warning(f"Fingerprint not found for track {track_id}")
                return False

            session.delete(fingerprint)
            session.commit()

            info(f"Deleted fingerprint for track {track_id}")
            return True

        except Exception as e:
            session.rollback()
            error(f"Failed to delete fingerprint for track {track_id}: {e}")
            return False
        finally:
            session.close()

    def get_all(self, limit: int | None = None, offset: int = 0) -> list[TrackFingerprint]:
        """
        Get all fingerprints with pagination.

        Args:
            limit: Maximum number of fingerprints to return. `None` returns
                ALL rows (intentional unbounded read — use carefully on
                large libraries). `0` returns an empty list.
            offset: Number of fingerprints to skip.

        Returns:
            List of TrackFingerprint objects
        """
        session = self.get_session()
        try:
            stmt = select(TrackFingerprint).order_by(TrackFingerprint.created_at.desc())

            # #3683: `if limit is not None` so `limit=0` returns an empty
            # list (not unbounded). Previously `if limit:` collapsed both
            # `0` and `None` to unbounded — root cause of OOM in
            # `refresh_cloud` (#3680) and `similarity.find_similar` fallback
            # (#3705).
            if limit is not None:
                stmt = stmt.limit(limit).offset(offset)

            fingerprints = session.execute(stmt).scalars().all()
            for fp in fingerprints:
                session.expunge(fp)
            return fingerprints

        finally:
            session.close()

    def get_count(self) -> int:
        """
        Get total count of fingerprints

        Returns:
            Total number of fingerprints
        """
        session = self.get_session()
        try:
            return session.execute(select(func.count()).select_from(TrackFingerprint)).scalar_one()
        finally:
            session.close()

    def get_reference_cloud(self) -> list[TrackFingerprint]:
        """Return all fingerprints flagged is_reference=True (schema v15).

        Used by the soft k-NN mastering target derivation to build the
        continuous reference manifold. Indexed via ix_fingerprints_is_reference
        so the lookup is fast even on large libraries.
        """
        session = self.get_session()
        try:
            stmt = select(TrackFingerprint).where(TrackFingerprint.is_reference == True)  # noqa: E712
            fingerprints = list(session.execute(stmt).scalars().all())
            for fp in fingerprints:
                session.expunge(fp)
            return fingerprints
        finally:
            session.close()

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

    def clear_all_reference_flags(self) -> int:
        """Set is_reference=False on every fingerprint. Returns rows updated."""
        from sqlalchemy import update
        session = self.get_session()
        try:
            result = session.execute(
                update(TrackFingerprint)
                .where(TrackFingerprint.is_reference == True)  # noqa: E712
                .values(is_reference=False)
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
        session = self.get_session()
        try:
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

            if limit:
                stmt = stmt.limit(limit)

            fingerprints = session.execute(stmt).scalars().all()
            for fp in fingerprints:
                session.expunge(fp)
            return fingerprints

        finally:
            session.close()

    def get_by_multi_dimension_range(
        self,
        ranges: dict[str, tuple[float, float]],
        limit: int | None = None
    ) -> list[TrackFingerprint]:
        """
        Get fingerprints within multiple dimension ranges

        More efficient pre-filtering for similarity search

        Args:
            ranges: Dictionary mapping dimension names to (min, max) tuples
                   e.g., {'lufs': (-20, -10), 'tempo_bpm': (100, 140)}
            limit: Maximum number of results

        Returns:
            List of TrackFingerprint objects matching all range criteria
        """
        session = self.get_session()
        try:
            # Build filter conditions
            conditions = []
            for dimension, (min_val, max_val) in ranges.items():
                if not hasattr(TrackFingerprint, dimension):
                    warning(f"Invalid dimension: {dimension}, skipping")
                    continue

                dim_attr = getattr(TrackFingerprint, dimension)
                conditions.append(and_(
                    dim_attr >= min_val,
                    dim_attr <= max_val
                ))

            if not conditions:
                warning("No valid dimension ranges provided")
                return []

            stmt = select(TrackFingerprint).where(and_(*conditions))

            if limit:
                stmt = stmt.limit(limit)

            fingerprints = session.execute(stmt).scalars().all()
            for fp in fingerprints:
                session.expunge(fp)
            return fingerprints

        finally:
            session.close()

    def exists(self, track_id: int) -> bool:
        """
        Check if a fingerprint exists for a track

        Args:
            track_id: ID of the track

        Returns:
            True if fingerprint exists, False otherwise
        """
        session = self.get_session()
        try:
            count = session.execute(
                select(func.count()).select_from(TrackFingerprint).where(
                    TrackFingerprint.track_id == track_id
                )
            ).scalar_one()
            return count > 0
        finally:
            session.close()

    def get_missing_fingerprints(self, limit: int | None = None) -> list[Track]:
        """
        Get tracks that don't have fingerprints yet

        Useful for batch fingerprint extraction

        Args:
            limit: Maximum number of tracks to return

        Returns:
            List of Track objects without fingerprints
        """
        session = self.get_session()
        try:
            stmt = select(Track).outerjoin(
                TrackFingerprint,
                Track.id == TrackFingerprint.track_id
            ).where(
                TrackFingerprint.id == None
            )

            if limit:
                stmt = stmt.limit(limit)

            tracks = session.execute(stmt).scalars().all()

            # CRITICAL: Detach all Track objects from session before returning
            # Prevents memory accumulation when workers process tracks from multiple queries
            # Without detaching, each worker holds a session reference for the entire track lifetime
            for track in tracks:
                session.expunge(track)

            return tracks

        finally:
            # CRITICAL: Clear session to free memory
            session.expunge_all()
            session.close()

    def upsert(self, track_id: int, fingerprint_data: dict[str, float]) -> TrackFingerprint | None:
        """
        Insert or update a fingerprint (upsert operation)

        Optimized to do single database round-trip with immediate session cleanup

        Args:
            track_id: ID of the track
            fingerprint_data: Dictionary with all 25 fingerprint dimensions

        Returns:
            TrackFingerprint object if successful, None if failed
        """
        # Validate column names before acquiring a session so ValueError
        # propagates to the caller instead of being swallowed (#2286).
        cols = list(fingerprint_data.keys())
        _validate_fingerprint_columns(cols)
        cols_str = ', '.join(cols)
        named_placeholders = ', '.join([f':{col}' for col in cols])

        # Use INSERT ... ON CONFLICT DO UPDATE rather than INSERT OR REPLACE.
        # REPLACE deletes the existing row and inserts a new one, which:
        #   - resets the `id` PK to a fresh auto-increment value
        #   - wipes `created_at` and any column not listed (e.g. the
        #     quantized `fingerprint_blob` set by store_fingerprint)
        #   - causes a race window between the implicit DELETE and INSERT
        # ON CONFLICT updates only the listed columns in-place and is also
        # atomic, which closes the concurrent-insert race (#3467, #3459).
        #
        # On INSERT we must supply `fingerprint_version` because it is
        # NOT NULL and its default is a Python-side ORM default (not a
        # SQL default), so raw INSERT does not see it. On UPDATE we only
        # refresh the 25 dimension columns — `fingerprint_blob` and
        # `fingerprint_version` stay as whatever store_fingerprint set.
        update_clause = ', '.join(f"{col} = excluded.{col}" for col in cols)

        session = self.get_session()
        try:
            params: dict[str, Any] = {
                'track_id': track_id,
                'fp_version': FINGERPRINT_ALGORITHM_VERSION,
                **fingerprint_data,
            }

            session.execute(
                text(
                    f"INSERT INTO track_fingerprints (track_id, fingerprint_version, {cols_str}) "
                    f"VALUES (:track_id, :fp_version, {named_placeholders}) "
                    f"ON CONFLICT (track_id) DO UPDATE SET {update_clause}"
                ),
                params,
            )
            session.commit()

            fingerprint = TrackFingerprint(track_id=track_id, **fingerprint_data)
            info(f"Upserted fingerprint for track {track_id}")
            return fingerprint

        except Exception as e:
            session.rollback()
            error(f"Failed to upsert fingerprint for track {track_id}: {e}")
            return None
        finally:
            session.expunge_all()
            session.close()

    def store_fingerprint(
        self,
        track_id: int,
        sub_bass_pct: float, bass_pct: float, low_mid_pct: float, mid_pct: float,
        upper_mid_pct: float, presence_pct: float, air_pct: float,
        lufs: float, crest_db: float, bass_mid_ratio: float,
        tempo_bpm: float, rhythm_stability: float, transient_density: float, silence_ratio: float,
        spectral_centroid: float, spectral_rolloff: float, spectral_flatness: float,
        harmonic_ratio: float, pitch_stability: float, chroma_energy: float,
        dynamic_range_variation: float, loudness_variation_std: float, peak_consistency: float,
        stereo_width: float, phase_correlation: float,
    ) -> TrackFingerprint | None:
        """
        Store fingerprint with automatic quantization (Phase 3A).

        Stores both the quantized blob (25 bytes) and the float values for backward compatibility.

        Args:
            track_id: Track ID
            (25 float parameters for each fingerprint dimension)

        Returns:
            TrackFingerprint object if successful, None if failed
        """
        # Build fingerprint dict from explicit named parameters (keys are always
        # known here, but validate anyway for defense-in-depth — #2286).
        fingerprint_dict = {
            'sub_bass_pct': sub_bass_pct, 'bass_pct': bass_pct, 'low_mid_pct': low_mid_pct,
            'mid_pct': mid_pct, 'upper_mid_pct': upper_mid_pct, 'presence_pct': presence_pct,
            'air_pct': air_pct, 'lufs': lufs, 'crest_db': crest_db, 'bass_mid_ratio': bass_mid_ratio,
            'tempo_bpm': tempo_bpm, 'rhythm_stability': rhythm_stability, 'transient_density': transient_density,
            'silence_ratio': silence_ratio, 'spectral_centroid': spectral_centroid,
            'spectral_rolloff': spectral_rolloff, 'spectral_flatness': spectral_flatness,
            'harmonic_ratio': harmonic_ratio, 'pitch_stability': pitch_stability, 'chroma_energy': chroma_energy,
            'dynamic_range_variation': dynamic_range_variation, 'loudness_variation_std': loudness_variation_std,
            'peak_consistency': peak_consistency, 'stereo_width': stereo_width, 'phase_correlation': phase_correlation,
        }

        # Validate before acquiring a session so ValueError reaches the caller (#2286).
        cols = list(fingerprint_dict.keys())
        _validate_fingerprint_columns(cols)
        cols_str = ', '.join(cols)
        named_placeholders = ', '.join([f':{col}' for col in cols])

        # ON CONFLICT DO UPDATE keeps the `id` PK stable and the existing
        # `created_at` intact (cf. #3467 sibling); only the listed columns
        # are written. fingerprint_blob and fingerprint_version are listed
        # here, so they're always refreshed on update.
        all_cols = cols + ['fingerprint_blob', 'fingerprint_version']
        update_clause = ', '.join(f"{col} = excluded.{col}" for col in all_cols)

        session = self.get_session()
        try:
            # Quantize fingerprint
            quantized_blob = FingerprintQuantizer.quantize(fingerprint_dict)

            params: dict[str, Any] = {
                'track_id': track_id,
                'fingerprint_blob': quantized_blob,
                'fp_version': FINGERPRINT_ALGORITHM_VERSION,
                **fingerprint_dict,
            }

            session.execute(
                text(f"""
                    INSERT INTO track_fingerprints
                    (track_id, {cols_str}, fingerprint_blob, fingerprint_version)
                    VALUES (:track_id, {named_placeholders}, :fingerprint_blob, :fp_version)
                    ON CONFLICT (track_id) DO UPDATE SET {update_clause}
                """),
                params,
            )
            session.commit()

            info(f"Stored fingerprint for track {track_id} (quantized blob: 25 bytes)")
            return None

        except Exception as e:
            session.rollback()
            error(f"Failed to store fingerprint for track {track_id}: {e}")
            return None
        finally:
            session.expunge_all()
            session.close()

    # update_status, get_fingerprint_status, get_fingerprint_stats, and
    # cleanup_incomplete_fingerprints have been moved to
    # FingerprintStatsRepository (fingerprint_stats_repository.py).

