"""
Fingerprint Stats Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Statistics, status tracking, and crash-recovery cleanup for fingerprints.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any
from collections.abc import Callable

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from ...utils.logging import error, info
from ...__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..models import Track, TrackFingerprint


class FingerprintStatsRepository:
    """Statistics, status tracking, and startup cleanup for fingerprints."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get_session(self) -> Session:
        return self.session_factory()

    def update_status(self, track_id: int, status: str, completed_at: str | None = None) -> bool:
        """Update fingerprint processing status for a track.

        Args:
            track_id: Track ID
            status: Status ('completed' or 'failed')
            completed_at: ISO timestamp when processing completed

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
        """Get fingerprint status for a specific track.

        Returns:
            Dict with fingerprint status details or None if not found.
        """
        session = self.get_session()
        try:
            fingerprint = session.execute(
                select(TrackFingerprint).where(TrackFingerprint.track_id == track_id)
            ).scalars().first()

            if not fingerprint:
                return None

            return {
                'track_id': fingerprint.track_id,
                'status': getattr(fingerprint, 'status', 'unknown'),
                'created_at': fingerprint.created_at,
                'updated_at': getattr(fingerprint, 'updated_at', None),
                'has_fingerprint': fingerprint is not None,
            }
        finally:
            session.close()

    def get_fingerprint_stats(self) -> dict[str, int]:
        """Get overall fingerprint statistics.

        Returns:
            Dict with 'total', 'fingerprinted', 'current', 'outdated',
            'pending', and 'progress_percent' counts.
        """
        session = self.get_session()
        try:
            total_tracks = session.execute(
                select(func.count(Track.id))
            ).scalar_one_or_none() or 0

            # Fully-computed fingerprints at the current algorithm version,
            # excluding new-track placeholder rows (lufs=-100.0) and stale
            # outdated-claim sentinels (fingerprint_version=0).
            current_count = session.execute(
                select(func.count(TrackFingerprint.id))
                .where(
                    TrackFingerprint.lufs != -100.0,
                    TrackFingerprint.fingerprint_version == FINGERPRINT_ALGORITHM_VERSION,
                )
            ).scalar_one_or_none() or 0

            # Outdated fingerprints: present but computed with an older version
            outdated_count = session.execute(
                select(func.count(TrackFingerprint.id))
                .where(
                    TrackFingerprint.lufs != -100.0,
                    TrackFingerprint.fingerprint_version > 0,
                    TrackFingerprint.fingerprint_version < FINGERPRINT_ALGORITHM_VERSION,
                )
            ).scalar_one_or_none() or 0

            # "fingerprinted" = any valid row (current or outdated)
            fingerprinted_count = current_count + outdated_count
            pending_count = max(0, total_tracks - fingerprinted_count)
            progress_percent = int((current_count / max(1, total_tracks)) * 100)

            return {
                'total': total_tracks,
                'fingerprinted': fingerprinted_count,
                'current': current_count,
                'outdated': outdated_count,
                'pending': pending_count,
                'progress_percent': progress_percent,
            }
        finally:
            session.close()

    def cleanup_incomplete_fingerprints(self) -> int:
        """Clean up incomplete fingerprints on startup (crash recovery).

        Handles two cases:

        1. New-track placeholders (lufs=-100.0): deleted so the track re-enters
           the unfingerprinted queue on the next worker pass.
        2. Stale outdated-fingerprint claims (fingerprint_version=0): reset to
           version 1 so they re-enter the outdated queue on the next worker pass.

        Returns:
            Total number of rows cleaned up (deleted + reset)

        Raises:
            Exception: If cleanup fails
        """
        session = self.get_session()
        try:
            # 1. Delete new-track placeholder rows (lufs=-100.0 sentinel, #2453).
            result = session.execute(
                delete(TrackFingerprint).where(TrackFingerprint.lufs == -100.0)
            )
            deleted_count = result.rowcount

            # 2. Reset stale outdated-fingerprint claims (fingerprint_version=0 sentinel).
            #    These are fingerprints that were claimed for re-extraction but the
            #    worker crashed before completing. Reset to version 1 so they are
            #    eligible for re-claiming next time.
            # #3711: use ORM update() instead of raw text() — table renames via
            # migrations would catch the change here.
            reset_result = session.execute(
                update(TrackFingerprint)
                .where(TrackFingerprint.fingerprint_version == 0)
                .values(fingerprint_version=1)
            )
            reset_count = reset_result.rowcount

            total = deleted_count + reset_count
            if total == 0:
                return 0

            session.commit()
            if deleted_count:
                info(f"Cleaned up {deleted_count} incomplete new-track fingerprint placeholder(s)")
            if reset_count:
                info(f"Reset {reset_count} stale outdated-fingerprint claim(s) (version=0 → 1)")
            return total
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
