"""
Fingerprint CRUD Mixin
~~~~~~~~~~~~~~~~~~~~~~

Basic write-path operations for ``FingerprintRepository`` — add / update /
delete a single fingerprint via the ORM. Extracted from
fingerprint_repository.py (#4511). The raw-SQL ``upsert()`` /
``store_fingerprint()`` paths used by the extraction pipeline live in the
sibling ``FingerprintUpsertMixin`` — split out separately to keep both
modules under the project's per-file line budget.

Mixed into ``FingerprintRepository`` alongside ``FingerprintUpsertMixin``,
``FingerprintQueryMixin`` and ``FingerprintSimilarityMixin`` — same
mixin-composes-BaseRepository layout as ``TrackRepository``'s
``track_repository_*.py`` split (#4511): each mixin inherits
``BaseRepository`` directly for ``get_session``/``_session_scope`` rather
than declaring a bare type annotation for them, so multiple sibling mixins
sharing the same base don't trip mypy's "incompatible definition in base
class" check when composed together on the facade.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from sqlalchemy import select

from ...utils.logging import debug, error, info, warning
from ..models import TrackFingerprint
from .base import BaseRepository


class FingerprintCrudMixin(BaseRepository):
    """Add/update/delete operations for fingerprint rows."""

    def add(self, track_id: int, fingerprint_data: dict[str, float]) -> TrackFingerprint | None:
        """
        Add a fingerprint for a track

        Args:
            track_id: ID of the track
            fingerprint_data: Dictionary with all 25 fingerprint dimensions

        Returns:
            TrackFingerprint object if successful, None if failed
        """
        with self._session_scope() as session:
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

    def update(self, track_id: int, fingerprint_data: dict[str, float]) -> TrackFingerprint | None:
        """
        Update an existing fingerprint

        Args:
            track_id: ID of the track
            fingerprint_data: Dictionary with fingerprint dimensions to update

        Returns:
            Updated TrackFingerprint object if successful, None if failed
        """
        with self._session_scope() as session:
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

    def delete(self, track_id: int) -> bool:
        """
        Delete a fingerprint

        Args:
            track_id: ID of the track

        Returns:
            True if successful, False otherwise
        """
        with self._session_scope() as session:
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
