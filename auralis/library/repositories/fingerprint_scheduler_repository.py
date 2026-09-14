"""
Fingerprint Scheduler Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pessimistic-lock scheduling for the fingerprinting worker queue.
Methods here atomically claim tracks so parallel workers never double-process.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy import delete, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...utils.logging import debug, error
from ...__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..models import Track, TrackFingerprint
from .base import BaseRepository


def release_claims(session: Session, track_id: int | None = None) -> tuple[int, int]:
    """Undo in-progress fingerprint claims; the caller commits.

    Reverses both claim sentinels so the track re-enters its queue:

    1. New-track placeholders (lufs=-100.0, #2453) are deleted, so the track
       matches ``claim_next_unfingerprinted_track`` again.
    2. Outdated-fingerprint claims (fingerprint_version=0) are reset to
       version 1, so the row matches ``claim_next_outdated_fingerprint`` again.

    Scoped to one track (a failed extraction, #5308) or, with ``track_id``
    None, every row (startup crash recovery).

    Returns:
        (placeholders deleted, outdated claims reset)
    """
    # #3711: ORM delete()/update() rather than raw text(), so a table rename
    # via migrations is caught here.
    placeholders = delete(TrackFingerprint).where(TrackFingerprint.lufs == -100.0)
    claimed = update(TrackFingerprint).where(TrackFingerprint.fingerprint_version == 0)
    if track_id is not None:
        placeholders = placeholders.where(TrackFingerprint.track_id == track_id)
        claimed = claimed.where(TrackFingerprint.track_id == track_id)
    # Bulk DML types as a plain Result; at runtime it is a CursorResult.
    deleted = cast(CursorResult[Any], session.execute(placeholders)).rowcount
    reset = cast(
        CursorResult[Any], session.execute(claimed.values(fingerprint_version=1))
    ).rowcount
    return deleted, reset


class FingerprintSchedulerRepository(BaseRepository):
    """Pessimistic-lock scheduling for fingerprint worker queue.

    Each public method atomically claims exactly one track so concurrent
    workers cannot process the same track twice.

    Claim cursors (#5310): each claim query used to walk its table from the
    lowest id on every call, past every row already claimed, so a
    full-library run was O(N^2) (44x slower per claim after 29k claims on a
    30k-track library). Each queue now remembers the highest track id it has
    claimed and searches after it. A search that finds nothing retries once
    from the start, which picks up rows that became eligible behind the
    cursor: a released claim (#5308), a race lost to another worker, a row
    re-queued by a version bump. So no eligible track waits longer than one
    pass. The cursors live on this instance (RepositoryFactory keeps one per
    process) and start at 0, so every process start is a full pass.
    """

    _UNFINGERPRINTED = "unfingerprinted"
    _OUTDATED = "outdated"

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        super().__init__(session_factory)
        self._cursor_lock = threading.Lock()
        self._cursors: dict[str, int] = {self._UNFINGERPRINTED: 0, self._OUTDATED: 0}

    def _find_after_cursor(self, queue: str, find: Callable[[int], Any]) -> Any:
        """Run ``find(after_id)`` from the cursor, wrapping to the start once."""
        with self._cursor_lock:
            after = self._cursors[queue]
        row = find(after)
        if row is None and after > 0:
            with self._cursor_lock:
                # Another claimer may have moved it meanwhile; only rewind ours.
                if self._cursors[queue] == after:
                    self._cursors[queue] = 0
            row = find(0)
        return row

    def _advance_cursor(self, queue: str, track_id: int) -> None:
        with self._cursor_lock:
            if track_id > self._cursors[queue]:
                self._cursors[queue] = track_id

    def claim_next_unfingerprinted_track(self) -> Track | None:
        """Atomically claim the next unfingerprinted track for processing.

        CRITICAL FIX FOR RACE CONDITION: Prevents multiple workers from processing
        the same track. Uses a placeholder fingerprint row (lufs=-100.0 sentinel)
        to atomically mark a track as in-progress. If the INSERT fails on UNIQUE
        constraint, another worker got there first — return None.

        Returns:
            Track object if successfully claimed, None if none available or race lost.
        """
        with self._session_scope() as session:
            try:
                # Next unfingerprinted track after the cursor, via LEFT JOIN.
                # Only id and filepath are needed, so no Track row is loaded.
                def find(after_id: int) -> Any:
                    return session.execute(
                        select(Track.id, Track.filepath).outerjoin(
                            TrackFingerprint,
                            Track.id == TrackFingerprint.track_id
                        ).where(
                            TrackFingerprint.id == None,  # noqa: E711 — SQL IS NULL
                            Track.filepath.isnot(None),
                            Track.id > after_id,
                        ).order_by(Track.id).limit(1)
                    ).first()

                unfingerprinted = self._find_after_cursor(self._UNFINGERPRINTED, find)

                if not unfingerprinted:
                    return None

                # Save track ID and filepath BEFORE creating placeholder (minimize transaction time)
                track_id = int(unfingerprinted[0])
                filepath = unfingerprinted[1]

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
                    self._advance_cursor(self._UNFINGERPRINTED, track_id)

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

        with self._session_scope() as session:
            try:
                # The unary `+` on fingerprint_version keeps SQLite off
                # idx_fingerprints_version. With that index the planner reads
                # every eligible row and sorts them by track_id on each claim,
                # which is O(N) again. Without it, it walks the track_id index
                # from the cursor and stops at the first match (#5310).
                def find(after_id: int) -> Any:
                    return session.execute(
                        text("""
                            SELECT tf.track_id, t.filepath
                            FROM track_fingerprints tf
                            JOIN tracks t ON t.id = tf.track_id
                            WHERE +tf.fingerprint_version > 0
                              AND +tf.fingerprint_version < :current_ver
                              AND tf.lufs != -100.0
                              AND t.filepath IS NOT NULL
                              AND tf.track_id > :after_id
                            ORDER BY tf.track_id
                            LIMIT 1
                        """),
                        {'current_ver': current_version, 'after_id': after_id},
                    ).first()

                row = self._find_after_cursor(self._OUTDATED, find)

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

                # A text() UPDATE types as a plain Result; at runtime it is a
                # CursorResult, which is what carries rowcount.
                if cast(CursorResult[Any], result).rowcount != 1:
                    # Another worker got there first
                    debug(f"Track {track_id} outdated fingerprint already claimed")
                    return None

                self._advance_cursor(self._OUTDATED, track_id)
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

    def release_claim(self, track_id: int) -> bool:
        """Release this track's claim after its extraction failed (#5308).

        Without this, the claim sentinel written by either claim method stayed
        in place, matching neither claim query, so the track was never retried
        until ``cleanup_incomplete_fingerprints`` ran at the next startup. A
        real fingerprint row that the extraction did manage to store matches
        neither sentinel and is left untouched.

        Returns:
            True if a claim was released, False if there was none.
        """
        with self._session_scope() as session:
            try:
                deleted, reset = release_claims(session, track_id)
                session.commit()
            except Exception:
                session.rollback()
                raise
        return bool(deleted or reset)
