"""
Fingerprint Query Mixin
~~~~~~~~~~~~~~~~~~~~~~~

Read-path operations for ``FingerprintRepository`` — single/bulk lookups,
paginated listing, counting, existence checks, and the missing-fingerprint
scan used to seed the extraction queue. Extracted from
fingerprint_repository.py (#4511).

Mixed into ``FingerprintRepository`` alongside ``FingerprintCrudMixin``,
``FingerprintUpsertMixin`` and ``FingerprintSimilarityMixin`` — same
mixin-composes-BaseRepository layout as ``TrackRepository``'s
``track_repository_*.py`` split (#4511): each mixin inherits
``BaseRepository`` directly for ``get_session``/``_session_scope`` rather
than declaring a bare type annotation for them, so multiple sibling mixins
sharing the same base don't trip mypy's "incompatible definition in base
class" check when composed together on the facade.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from sqlalchemy import func, select

from ..models import Track, TrackFingerprint
from .base import BaseRepository
from .fingerprint_shared import _current_fingerprint_clause


class FingerprintQueryMixin(BaseRepository):
    """Read/lookup operations for fingerprint rows."""

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
        with self._session_scope() as session:
            fingerprints = session.execute(
                select(TrackFingerprint).where(
                    TrackFingerprint.track_id.in_(track_ids),
                    _current_fingerprint_clause(),
                )
            ).scalars().all()
            for fp in fingerprints:
                session.expunge(fp)
            return list(fingerprints)

    def get_by_track_id(self, track_id: int) -> TrackFingerprint | None:
        """
        Get fingerprint by track ID

        Excludes an in-progress claim placeholder or stale-algorithm-version
        row (#4822) — same as "no fingerprint yet" to every caller.

        Args:
            track_id: ID of the track

        Returns:
            TrackFingerprint object if found and current, None otherwise
        """
        with self._session_scope() as session:
            fingerprint = session.execute(
                select(TrackFingerprint).where(
                    TrackFingerprint.track_id == track_id,
                    _current_fingerprint_clause(),
                )
            ).scalars().first()
            if fingerprint:
                session.expunge(fingerprint)
            return fingerprint

    def get_all(self, limit: int | None = None, offset: int = 0) -> list[TrackFingerprint]:
        """
        Get all current, complete fingerprints with pagination.

        Excludes in-progress claim placeholders and stale-algorithm-version
        rows (#4822) — callers (similarity candidates, K-NN graph builds,
        the normalizer's percentile fit) never see them.

        Args:
            limit: Maximum number of fingerprints to return. `None` returns
                ALL matching rows (intentional unbounded read — use carefully
                on large libraries). `0` returns an empty list.
            offset: Number of fingerprints to skip.

        Returns:
            List of TrackFingerprint objects
        """
        with self._session_scope() as session:
            stmt = (
                select(TrackFingerprint)
                .where(_current_fingerprint_clause())
                .order_by(TrackFingerprint.created_at.desc())
            )

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

    def get_all_with_track_stats(self, limit: int | None = None, offset: int = 0) -> list[TrackFingerprint]:
        """Like get_all(), but each returned row also carries `.play_count`
        and `.favorite` copied from its Track (#3480 Layer 1).

        The reference-cloud seeder weighs references by listening behavior,
        which track_fingerprints doesn't store. Rather than eager-loading
        the full `track` relationship (touched by every get_all() caller —
        similarity, K-NN graph, the normalizer — none of which need it),
        this is a separate, seeder-only read path with its own join.

        Args:
            limit: Maximum number of fingerprints to return (see get_all()).
            offset: Number of fingerprints to skip.

        Returns:
            List of TrackFingerprint objects with play_count/favorite attached.
        """
        with self._session_scope() as session:
            stmt = (
                select(TrackFingerprint, Track.play_count, Track.favorite)
                .join(Track, Track.id == TrackFingerprint.track_id)
                .where(_current_fingerprint_clause())
                .order_by(TrackFingerprint.created_at.desc())
            )
            if limit is not None:
                stmt = stmt.limit(limit).offset(offset)

            fingerprints = []
            for fp, play_count, favorite in session.execute(stmt).all():
                session.expunge(fp)
                fp.play_count = play_count or 0
                fp.favorite = bool(favorite)
                fingerprints.append(fp)
            return fingerprints

    def get_count(self) -> int:
        """
        Get total count of fingerprints

        Returns:
            Total number of fingerprints
        """
        with self._session_scope() as session:
            return session.execute(select(func.count()).select_from(TrackFingerprint)).scalar_one()

    def exists(self, track_id: int) -> bool:
        """
        Check if a current, complete fingerprint exists for a track.

        False for an in-progress claim placeholder or a stale-algorithm-
        version row (#4822) — callers already treat False as "not ready,
        enqueue for (re-)fingerprinting" rather than an error.

        Args:
            track_id: ID of the track

        Returns:
            True if a current fingerprint exists, False otherwise
        """
        with self._session_scope() as session:
            count = session.execute(
                select(func.count()).select_from(TrackFingerprint).where(
                    TrackFingerprint.track_id == track_id,
                    _current_fingerprint_clause(),
                )
            ).scalar_one()
            return count > 0

    def get_missing_fingerprints(self, limit: int | None = None) -> list[Track]:
        """
        Get tracks that don't have fingerprints yet

        Useful for batch fingerprint extraction

        Args:
            limit: Maximum number of tracks to return

        Returns:
            List of Track objects without fingerprints
        """
        with self._session_scope() as session:
            stmt = select(Track).outerjoin(
                TrackFingerprint,
                Track.id == TrackFingerprint.track_id
            ).where(
                TrackFingerprint.id == None
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            tracks = session.execute(stmt).scalars().all()

            # CRITICAL: Detach all Track objects from session before returning
            # Prevents memory accumulation when workers process tracks from multiple queries
            # Without detaching, each worker holds a session reference for the entire track lifetime
            for track in tracks:
                session.expunge(track)

            # CRITICAL: Clear session to free memory
            session.expunge_all()

            return tracks
