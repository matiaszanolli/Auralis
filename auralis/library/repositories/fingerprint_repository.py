# -*- coding: utf-8 -*-

"""
Fingerprint Repository
~~~~~~~~~~~~~~~~~~~~~

Data access layer for track fingerprint operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Optional, List, Dict, Any, Callable
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..models import TrackFingerprint, Track
from ...utils.logging import info, warning, error, debug


class FingerprintRepository:
    """Repository for fingerprint database operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """
        Initialize fingerprint repository

        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def add(self, track_id: int, fingerprint_data: Dict[str, float]) -> Optional[TrackFingerprint]:
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

    def get_by_track_id(self, track_id: int) -> Optional[TrackFingerprint]:
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
            return fingerprint
        finally:
            session.close()

    def update(self, track_id: int, fingerprint_data: Dict[str, float]) -> Optional[TrackFingerprint]:
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

    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> List[TrackFingerprint]:
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

            return query.all()

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
        limit: Optional[int] = None
    ) -> List[TrackFingerprint]:
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

            return query.all()

        finally:
            session.close()

    def get_by_multi_dimension_range(
        self,
        ranges: Dict[str, tuple],
        limit: Optional[int] = None
    ) -> List[TrackFingerprint]:
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

            return query.all()

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

    def get_missing_fingerprints(self, limit: Optional[int] = None) -> List[Track]:
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

    def claim_next_unfingerprinted_track(self) -> Optional[Track]:
        """
        Atomically claim the next unfingerprinted track for processing.

        CRITICAL FIX FOR RACE CONDITION: Prevents multiple workers from processing the same track.
        Uses database transaction to atomically:
        1. Find an unfingerprinted track
        2. Create a placeholder fingerprint to "claim" it
        3. Return the track only if claiming succeeded

        If another worker already claimed the track, INSERT fails with UNIQUE constraint
        and we return None (next iteration will fetch a different track).

        Returns:
            Track object if successfully claimed, None if no tracks available
        """
        session = self.get_session()
        try:
            # Find first unfingerprinted track
            unfingerprinted = session.query(Track).outerjoin(
                TrackFingerprint,
                Track.id == TrackFingerprint.track_id
            ).filter(
                TrackFingerprint.id == None
            ).order_by(Track.id).first()

            if not unfingerprinted:
                # No unfingerprinted tracks left
                return None

            # Try to "claim" this track by creating a placeholder fingerprint
            # Initialize with zeros for all 27 dimensions (will be overwritten during upsert)
            try:
                placeholder = TrackFingerprint(
                    track_id=unfingerprinted.id,
                    # Frequency Distribution (7D)
                    sub_bass_pct=0.0,
                    bass_pct=0.0,
                    low_mid_pct=0.0,
                    mid_pct=0.0,
                    upper_mid_pct=0.0,
                    presence_pct=0.0,
                    air_pct=0.0,
                    # Dynamics (3D)
                    lufs=-100.0,
                    crest_db=0.0,
                    bass_mid_ratio=0.0,
                    # Temporal (4D)
                    tempo_bpm=0.0,
                    rhythm_stability=0.0,
                    transient_density=0.0,
                    silence_ratio=0.0,
                    # Spectral (3D)
                    spectral_centroid=0.0,
                    spectral_rolloff=0.0,
                    spectral_flatness=0.0,
                    # Harmonic (3D)
                    harmonic_ratio=0.0,
                    pitch_stability=0.0,
                    chroma_energy=0.0,
                    # Variation (3D)
                    dynamic_range_variation=0.0,
                    loudness_variation_std=0.0,
                    peak_consistency=0.0,
                    # Stereo (2D)
                    stereo_width=0.0,
                    phase_correlation=0.0,
                    # Metadata
                    fingerprint_version=1,
                )
                session.add(placeholder)
                session.commit()

                # Successfully claimed! Refresh to ensure all Track fields are loaded
                # before detaching, so the track object is fully functional for processing
                session.refresh(unfingerprinted)
                session.expunge(unfingerprinted)
                debug(f"Track {unfingerprinted.id} claimed by worker")
                return unfingerprinted

            except Exception as claim_error:
                # Another worker already claimed this track (UNIQUE constraint)
                # Rollback and return None - next iteration will get a different track
                session.rollback()
                debug(f"Track {unfingerprinted.id} already claimed: {claim_error}")
                return None

        except Exception as e:
            session.rollback()
            error(f"Error claiming next unfingerprinted track: {e}")
            return None
        finally:
            session.expunge_all()
            session.close()

    def upsert(self, track_id: int, fingerprint_data: Dict[str, float]) -> Optional[TrackFingerprint]:
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
            # Try update first (single query, works for both insert and update)
            fingerprint = session.query(TrackFingerprint).filter(
                TrackFingerprint.track_id == track_id
            ).first()

            if fingerprint:
                # Update existing
                for key, value in fingerprint_data.items():
                    if hasattr(fingerprint, key):
                        setattr(fingerprint, key, value)
            else:
                # Insert new
                fingerprint = TrackFingerprint(
                    track_id=track_id,
                    **fingerprint_data
                )
                session.add(fingerprint)

            session.commit()
            session.refresh(fingerprint)

            # CRITICAL: Detach object from session before returning
            # Prevents memory accumulation with multi-threaded workers
            session.expunge(fingerprint)

            info(f"Upserted fingerprint for track {track_id}")
            return fingerprint

        except Exception as e:
            session.rollback()
            error(f"Failed to upsert fingerprint for track {track_id}: {e}")
            return None
        finally:
            # CRITICAL: Explicitly clear session to free memory
            # With 16 concurrent workers, this prevents unbounded memory growth
            session.expunge_all()
            session.close()
