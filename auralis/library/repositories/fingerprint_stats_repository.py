"""
Fingerprint Stats Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Statistics and crash-recovery cleanup for fingerprints.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


from sqlalchemy import func, select

from ...utils.logging import info
from ...__version__ import FINGERPRINT_ALGORITHM_VERSION
from .fingerprint_shared import PLACEHOLDER_LUFS_SENTINEL
from ..models import Track, TrackFingerprint
from .base import BaseRepository
from .fingerprint_scheduler_repository import release_claims


class FingerprintStatsRepository(BaseRepository):
    """Statistics and startup cleanup for fingerprints."""

    def get_fingerprint_stats(self) -> dict[str, int]:
        """Get overall fingerprint statistics.

        Returns:
            Dict with 'total', 'fingerprinted', 'current', 'outdated',
            'pending', and 'progress_percent' counts.
        """
        with self._session_scope() as session:
            total_tracks = session.execute(
                select(func.count(Track.id))
            ).scalar_one_or_none() or 0

            # Fully-computed fingerprints at the current algorithm version,
            # excluding new-track placeholder rows (lufs=-100.0) and stale
            # outdated-claim sentinels (fingerprint_version=0).
            current_count = session.execute(
                select(func.count(TrackFingerprint.id))
                .where(
                    # Sentinel exclusion is _current_fingerprint_clause()'s
                    # first condition (#6225) — one home for the predicate.
                    TrackFingerprint.lufs != PLACEHOLDER_LUFS_SENTINEL,
                    TrackFingerprint.fingerprint_version == FINGERPRINT_ALGORITHM_VERSION,
                )
            ).scalar_one_or_none() or 0

            # Outdated fingerprints: present but computed with an older version
            outdated_count = session.execute(
                select(func.count(TrackFingerprint.id))
                .where(
                    TrackFingerprint.lufs != PLACEHOLDER_LUFS_SENTINEL,
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
        with self._session_scope() as session:
            try:
                # Same release the worker applies to one track after a failed
                # extraction (#5308), so the two cannot disagree on what a
                # claim sentinel is.
                deleted_count, reset_count = release_claims(session)

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
