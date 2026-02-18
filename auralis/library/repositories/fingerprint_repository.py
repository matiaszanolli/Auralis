"""
Fingerprint Repository
~~~~~~~~~~~~~~~~~~~~~

Data access layer for track fingerprint operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pathlib import Path
from typing import Any
from collections.abc import Callable

from sqlalchemy import and_, text
from sqlalchemy.orm import Session

from ...utils.logging import debug, error, info, warning
from ..fingerprint_quantizer import FingerprintQuantizer
from ..models import Track, TrackFingerprint


class FingerprintRepository:
    """Repository for fingerprint database operations"""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        db_path: str | Path | None = None,
    ) -> None:
        """
        Initialize fingerprint repository

        Args:
            session_factory: SQLAlchemy session factory
            db_path: Path to the SQLite database file used for raw writes.
                     Defaults to ~/.auralis/library.db when not provided.
        """
        self.session_factory = session_factory
        self._db_path: Path = (
            Path(db_path) if db_path is not None else Path.home() / '.auralis' / 'library.db'
        )

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
            existing = session.query(TrackFingerprint).filter(
                TrackFingerprint.track_id == track_id
            ).first()

            if existing:
                debug(f"Fingerprint already exists for track {track_id}, updating")
                session.close()
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
            fingerprint = session.query(TrackFingerprint).filter(
                TrackFingerprint.track_id == track_id
            ).first()
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
            fingerprint = session.query(TrackFingerprint).filter(
                TrackFingerprint.track_id == track_id
            ).first()

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
            fingerprint = session.query(TrackFingerprint).filter(
                TrackFingerprint.track_id == track_id
            ).first()

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
        Get all fingerprints with pagination

        Args:
            limit: Maximum number of fingerprints to return
            offset: Number of fingerprints to skip

        Returns:
            List of TrackFingerprint objects
        """
        session = self.get_session()
        try:
            query = session.query(TrackFingerprint).order_by(TrackFingerprint.created_at.desc())

            if limit:
                query = query.limit(limit).offset(offset)

            fingerprints = query.all()
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
            return session.query(TrackFingerprint).count()
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
            query = session.query(TrackFingerprint).filter(
                and_(
                    dim_attr >= min_value,
                    dim_attr <= max_value
                )
            )

            if limit:
                query = query.limit(limit)

            fingerprints = query.all()
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

            query = session.query(TrackFingerprint).filter(and_(*conditions))

            if limit:
                query = query.limit(limit)

            fingerprints = query.all()
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
            count = session.query(TrackFingerprint).filter(
                TrackFingerprint.track_id == track_id
            ).count()
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
            query = session.query(Track).outerjoin(
                TrackFingerprint,
                Track.id == TrackFingerprint.track_id
            ).filter(
                TrackFingerprint.id == None
            )

            if limit:
                query = query.limit(limit)

            tracks = query.all()

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

    def claim_next_unfingerprinted_track(self) -> Track | None:
        """
        Atomically claim the next unfingerprinted track for processing.

        CRITICAL FIX FOR RACE CONDITION: Prevents multiple workers from processing the same track.
        Optimized for minimal transaction time to restore parallelism.

        Uses database transaction to atomically:
        1. Find an unfingerprinted track (fast simple query, not JOIN)
        2. Create a placeholder fingerprint to "claim" it
        3. Return the track only if claiming succeeded

        If another worker already claimed the track, INSERT fails with UNIQUE constraint
        and we return None (next iteration will fetch a different track).

        Returns:
            Track object if successfully claimed, None if no tracks available
        """
        session = self.get_session()
        try:
            # Find first unfingerprinted track using efficient LEFT JOIN
            unfingerprinted = session.query(Track).outerjoin(
                TrackFingerprint,
                Track.id == TrackFingerprint.track_id
            ).filter(
                TrackFingerprint.id == None,
                Track.filepath.isnot(None)
            ).order_by(Track.id).first()

            if not unfingerprinted:
                # No unfingerprinted tracks left
                return None

            # Save track ID and filepath BEFORE creating placeholder (minimize transaction time)
            track_id = unfingerprinted.id
            filepath = unfingerprinted.filepath

            # Try to "claim" this track by creating a placeholder fingerprint
            # Minimal initialization - only required fields set, rest will be overwritten during upsert
            try:
                placeholder = TrackFingerprint(
                    track_id=track_id,
                    # Initialize all 27 dimensions with zeros (will be overwritten)
                    sub_bass_pct=0.0, bass_pct=0.0, low_mid_pct=0.0, mid_pct=0.0,
                    upper_mid_pct=0.0, presence_pct=0.0, air_pct=0.0,
                    lufs=-100.0, crest_db=0.0, bass_mid_ratio=0.0,
                    tempo_bpm=0.0, rhythm_stability=0.0, transient_density=0.0, silence_ratio=0.0,
                    spectral_centroid=0.0, spectral_rolloff=0.0, spectral_flatness=0.0,
                    harmonic_ratio=0.0, pitch_stability=0.0, chroma_energy=0.0,
                    dynamic_range_variation=0.0, loudness_variation_std=0.0, peak_consistency=0.0,
                    stereo_width=0.0, phase_correlation=0.0,
                    fingerprint_version=1,
                )
                session.add(placeholder)
                session.commit()
                session.expunge_all()  # Clear session immediately after commit

                # Create a simple Track object with just the essential fields
                # (avoid keeping session references that slow down claiming)
                claimed_track = Track()
                claimed_track.id = track_id
                claimed_track.filepath = filepath

                debug(f"Track {track_id} claimed by worker")
                return claimed_track

            except Exception:
                # Another worker already claimed this track (UNIQUE constraint)
                # Rollback and return None - next iteration will get a different track
                session.rollback()
                debug(f"Track {track_id} already claimed by another worker")
                return None

        except Exception as e:
            session.rollback()
            error(f"Error claiming next unfingerprinted track: {e}")
            return None
        finally:
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
        session = self.get_session()
        try:
            cols = list(fingerprint_data.keys())
            cols_str = ', '.join(cols)
            named_placeholders = ', '.join([f':{col}' for col in cols])
            params: dict[str, Any] = {'track_id': track_id, **fingerprint_data}

            session.execute(
                text(f"INSERT OR REPLACE INTO track_fingerprints (track_id, {cols_str}) VALUES (:track_id, {named_placeholders})"),
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
        session = self.get_session()
        try:
            # Build fingerprint dict
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

            # Quantize fingerprint
            quantized_blob = FingerprintQuantizer.quantize(fingerprint_dict)

            cols = list(fingerprint_dict.keys())
            cols_str = ', '.join(cols)
            named_placeholders = ', '.join([f':{col}' for col in cols])
            params: dict[str, Any] = {
                'track_id': track_id,
                'fingerprint_blob': quantized_blob,
                **fingerprint_dict,
            }

            session.execute(
                text(f"""
                    INSERT OR REPLACE INTO track_fingerprints
                    (track_id, {cols_str}, fingerprint_blob, fingerprint_version)
                    VALUES (:track_id, {named_placeholders}, :fingerprint_blob, 1)
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

    def update_status(self, track_id: int, status: str, completed_at: str | None = None) -> bool:
        """
        Update fingerprint processing status for a track.

        Args:
            track_id: Track ID
            status: Status ('completed' or 'failed')
            completed_at: ISO timestamp when processing completed (for completed status)

        Returns:
            True if successful, False otherwise
        """
        session = self.get_session()
        try:
            if status == 'completed':
                session.execute(
                    text("""UPDATE track_fingerprints
                               SET fingerprint_status = :status,
                                   fingerprint_computed_at = :completed_at,
                                   fingerprint_started_at = NULL
                               WHERE track_id = :track_id"""),
                    {'status': status, 'completed_at': completed_at, 'track_id': track_id},
                )
            else:
                session.execute(
                    text("""UPDATE track_fingerprints
                               SET fingerprint_status = :status,
                                   fingerprint_started_at = NULL
                               WHERE track_id = :track_id"""),
                    {'status': status, 'track_id': track_id},
                )
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            error(f"Failed to update status for track {track_id}: {e}")
            return False
        finally:
            session.expunge_all()
            session.close()

    def get_fingerprint_status(self, track_id: int) -> dict[str, Any] | None:
        """
        Get fingerprint status for a specific track.

        Args:
            track_id: ID of the track

        Returns:
            Dict with fingerprint status details or None if not found
        """
        session = self.get_session()
        try:
            fingerprint = (
                session.query(TrackFingerprint)
                .filter(TrackFingerprint.track_id == track_id)
                .first()
            )

            if not fingerprint:
                return None

            return {
                'track_id': fingerprint.track_id,
                'status': getattr(fingerprint, 'status', 'unknown'),
                'created_at': fingerprint.created_at,
                'updated_at': getattr(fingerprint, 'updated_at', None),
                'has_fingerprint': fingerprint is not None
            }
        finally:
            session.close()

    def get_fingerprint_stats(self) -> dict[str, int]:
        """
        Get overall fingerprint statistics.

        Returns:
            Dict with 'total', 'fingerprinted', and 'pending' counts
        """
        session = self.get_session()
        try:
            from sqlalchemy import func

            # Count total tracks
            total_tracks = session.query(func.count(Track.id)).scalar() or 0

            # Count tracks with fingerprints
            fingerprinted_count = (
                session.query(func.count(TrackFingerprint.id))
                .scalar() or 0
            )

            pending_count = max(0, total_tracks - fingerprinted_count)
            progress_percent = int((fingerprinted_count / max(1, total_tracks)) * 100)

            return {
                'total': total_tracks,
                'fingerprinted': fingerprinted_count,
                'pending': pending_count,
                'progress_percent': progress_percent
            }
        finally:
            session.close()

    def cleanup_incomplete_fingerprints(self) -> int:
        """
        Clean up incomplete fingerprints (placeholders with LUFS=-100.0).

        Returns:
            Number of incomplete fingerprints deleted

        Raises:
            Exception: If cleanup fails
        """
        session = self.get_session()
        try:
            # Find incomplete placeholders (fingerprints with LUFS=-100.0)
            incomplete_fps = (
                session.query(TrackFingerprint)
                .filter(TrackFingerprint.lufs == -100.0)
                .all()
            )

            if not incomplete_fps:
                return 0

            incomplete_count = len(incomplete_fps)

            # Delete incomplete fingerprints
            for fp in incomplete_fps:
                session.delete(fp)

            session.commit()
            return incomplete_count
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
