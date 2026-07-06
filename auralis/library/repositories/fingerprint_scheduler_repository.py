"""
Fingerprint Scheduler Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pessimistic-lock scheduling for the fingerprinting worker queue.
Methods here atomically claim tracks so parallel workers never double-process.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from ...utils.logging import debug, error
from ...__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..models import Track, TrackFingerprint
from .base import BaseRepository


class FingerprintSchedulerRepository(BaseRepository):
    """Pessimistic-lock scheduling for fingerprint worker queue.

    Each public method atomically claims exactly one track so concurrent
    workers cannot process the same track twice.
    """

    def claim_next_unfingerprinted_track(self) -> Track | None:
        """Atomically claim the next unfingerprinted track for processing.

        CRITICAL FIX FOR RACE CONDITION: Prevents multiple workers from processing
        the same track. Uses a placeholder fingerprint row (lufs=-100.0 sentinel)
        to atomically mark a track as in-progress. If the INSERT fails on UNIQUE
        constraint, another worker got there first — return None.

        Returns:
            Track object if successfully claimed, None if none available or race lost.
        """
        session = self.get_session()
        try:
            # Find first unfingerprinted track using efficient LEFT JOIN
            unfingerprinted = session.execute(
                select(Track).outerjoin(
                    TrackFingerprint,
                    Track.id == TrackFingerprint.track_id
                ).where(
                    TrackFingerprint.id == None,
                    Track.filepath.isnot(None)
                ).order_by(Track.id)
            ).scalars().first()

            if not unfingerprinted:
                return None

            # Save track ID and filepath BEFORE creating placeholder (minimize transaction time)
            track_id = unfingerprinted.id
            filepath = unfingerprinted.filepath

            # Try to "claim" this track by creating a placeholder fingerprint.
            # Minimal initialization — only required fields set, rest will be
            # overwritten during upsert.
            try:
                placeholder = TrackFingerprint(
                    track_id=track_id,
                    # Initialize all 25 dimensions with zeros (will be overwritten)
                    sub_bass_pct=0.0, bass_pct=0.0, low_mid_pct=0.0, mid_pct=0.0,
                    upper_mid_pct=0.0, presence_pct=0.0, air_pct=0.0,
                    lufs=-100.0, crest_db=0.0, bass_mid_ratio=0.0,
                    tempo_bpm=0.0, rhythm_stability=0.0, transient_density=0.0, silence_ratio=0.0,
                    spectral_centroid=0.0, spectral_rolloff=0.0, spectral_flatness=0.0,
                    harmonic_ratio=0.0, pitch_stability=0.0, chroma_energy=0.0,
                    dynamic_range_variation=0.0, loudness_variation_std=0.0, peak_consistency=0.0,
                    stereo_width=0.0, phase_correlation=0.0,
                    fingerprint_version=FINGERPRINT_ALGORITHM_VERSION,
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

            except IntegrityError:
                # Another worker already claimed this track (UNIQUE constraint)
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

    def claim_next_outdated_fingerprint(self, current_version: int) -> Track | None:
        """Atomically claim the next fingerprint whose algorithm version is stale.

        Called by workers after the new-track queue is exhausted. Uses a
        version-sentinel strategy analogous to claim_next_unfingerprinted_track:

        1. Find a row with 0 < fingerprint_version < current_version.
        2. Set fingerprint_version = 0 to "claim" it atomically (rowcount check).
        3. Return the Track so the worker can re-extract and upsert.

        On worker crash, cleanup_incomplete_fingerprints() resets version-0 rows
        back to 1 so they re-enter the outdated queue on next startup.

        Args:
            current_version: The authoritative algorithm version (FINGERPRINT_ALGORITHM_VERSION).

        Returns:
            Track object if successfully claimed, None if nothing to update.
        """
        if current_version <= 1:
            # No fingerprints can be "outdated" if the current version is 1
            # (version 0 is only the crash-recovery sentinel, not a real version).
            return None

        session = self.get_session()
        try:
            row = session.execute(
                text("""
                    SELECT tf.track_id, t.filepath
                    FROM track_fingerprints tf
                    JOIN tracks t ON t.id = tf.track_id
                    WHERE tf.fingerprint_version > 0
                      AND tf.fingerprint_version < :current_ver
                      AND tf.lufs != -100.0
                      AND t.filepath IS NOT NULL
                    ORDER BY tf.track_id
                    LIMIT 1
                """),
                {'current_ver': current_version},
            ).first()

            if not row:
                return None

            track_id: int = row[0]
            filepath: str = row[1]

            # Claim atomically: set version=0 only if it still has the old version
            result = session.execute(
                text("""
                    UPDATE track_fingerprints
                    SET fingerprint_version = 0
                    WHERE track_id = :tid
                      AND fingerprint_version > 0
                      AND fingerprint_version < :current_ver
                """),
                {'tid': track_id, 'current_ver': current_version},
            )
            session.commit()

            if result.rowcount != 1:
                # Another worker got there first
                debug(f"Track {track_id} outdated fingerprint already claimed")
                return None

            claimed = Track()
            claimed.id = track_id
            claimed.filepath = filepath
            debug(f"Track {track_id} outdated fingerprint claimed for re-extraction")
            return claimed

        except Exception as e:
            session.rollback()
            error(f"Error claiming outdated fingerprint: {e}")
            return None
        finally:
            session.expunge_all()
            session.close()
