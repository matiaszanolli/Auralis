# -*- coding: utf-8 -*-

"""
Fingerprint Repository
~~~~~~~~~~~~~~~~~~~~~

Data access layer for track fingerprint operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..models import TrackFingerprint, Track
from ...utils.logging import info, warning, error, debug


class FingerprintRepository:
    """Repository for fingerprint database operations"""

    def __init__(self, session_factory):
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
                return self.update(track_id, fingerprint_data)

            # Create new fingerprint
            fingerprint = TrackFingerprint(
                track_id=track_id,
                **fingerprint_data
            )

            session.add(fingerprint)
            session.commit()
            session.refresh(fingerprint)

            info(f"Added fingerprint for track {track_id}")
            return fingerprint

        except Exception as e:
            session.rollback()
            error(f"Failed to add fingerprint for track {track_id}: {e}")
            return None
        finally:
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

            info(f"Updated fingerprint for track {track_id}")
            return fingerprint

        except Exception as e:
            session.rollback()
            error(f"Failed to update fingerprint for track {track_id}: {e}")
            return None
        finally:
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

            return query.all()

        finally:
            session.close()

    def upsert(self, track_id: int, fingerprint_data: Dict[str, float]) -> Optional[TrackFingerprint]:
        """
        Insert or update a fingerprint (upsert operation)

        Args:
            track_id: ID of the track
            fingerprint_data: Dictionary with all 25 fingerprint dimensions

        Returns:
            TrackFingerprint object if successful, None if failed
        """
        if self.exists(track_id):
            return self.update(track_id, fingerprint_data)
        else:
            return self.add(track_id, fingerprint_data)
