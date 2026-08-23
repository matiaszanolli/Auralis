"""
Playlist Membership Mixin
~~~~~~~~~~~~~~~~~~~~~~~~~

Adding tracks to a playlist for ``PlaylistRepository``, extracted from
``playlist_repository.py`` (#4511) to stay under the project's 300-line
convention. Pairs with ``playlist_ordering_mixin.py`` (remove/clear/
reorder) — together they cover track membership and position management
— and with ``playlist_crud_mixin.py`` / ``playlist_query_mixin.py``
(single-playlist CRUD and listing/search). All four are always mixed into
``PlaylistRepository`` together.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from sqlalchemy import delete, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...utils.logging import debug, error
from ..models import Playlist, Track
from ..models.base import track_playlist
from .base import BaseRepository


class PlaylistMembershipMixin(BaseRepository):
    """Track-add operations, sharing the repository's session factory.

    Inherits ``BaseRepository`` directly for ``get_session``/
    ``_session_scope`` (#4604) — same mixin-composes-BaseRepository layout
    the fingerprint mixins use (fingerprint_crud_mixin.py et al, #4511): a
    bare ``Callable[[], AbstractContextManager[Session]]`` annotation for
    ``_session_scope`` does not type-check across sibling mixins composed
    on the same facade (mypy flags it as an incompatible base-class
    definition, unlike the looser plain-attribute check ``get_session``'s
    bare annotation got away with), so direct inheritance is required here.
    """

    def _insert_track_at_next_position(self, session: Session, playlist_id: int, track_id: int) -> None:
        """Insert a (playlist_id, track_id) row at MAX(position)+1, atomically.

        Shared by ``add_track`` and ``add_tracks`` (fixes duplicated SQL, #4248).
        Folds the MAX(position)+1 derivation INTO the INSERT statement via
        INSERT...SELECT so SQLite serialises the read and the write as one
        atomic step — a separate SELECT-then-INSERT leaves a window where two
        concurrent appends both see the same MAX and land on the same
        position. ``INSERT OR IGNORE`` makes the call idempotent if the
        composite PK (track_id, playlist_id) already exists.

        text() form is needed because SQLAlchemy Core's insert().from_select()
        doesn't pass through OR IGNORE cleanly with bound parameters in a way
        SQLite likes. Caller is responsible for commit/rollback.
        """
        session.execute(
            text(
                "INSERT OR IGNORE INTO track_playlist "
                "(track_id, playlist_id, position) "
                "SELECT :tid, :pid, "
                "COALESCE(MAX(position), -1) + 1 "
                "FROM track_playlist WHERE playlist_id = :pid"
            ),
            {"tid": track_id, "pid": playlist_id},
        )

    def add_track(self, playlist_id: int, track_id: int, position: int | None = None) -> bool:
        """Add a track to a playlist at a specific position.

        #3724 + #3725: this now runs as a single transaction that issues
        an INSERT OR IGNORE on the association table (relying on the
        composite PK added in schema v016 for the uniqueness
        guarantee) and a SELECT MAX(position)+1 to assign a deterministic
        position. The previous read-modify-write via
        ``playlist.tracks.append`` had two open races:

        - **Duplicate inserts**: SELECT EXISTS → INSERT had a TOCTOU
          window where two concurrent callers both passed the check
          and both INSERTed. There was no DB-level uniqueness to fail
          them, so duplicates accumulated invisibly. v016's PRIMARY KEY
          on (track_id, playlist_id) plus SQLite's
          ``INSERT OR IGNORE`` collapses the race: at most one wins,
          the other is a silent no-op and the caller still gets True.
        - **Position races**: ``len(playlist.tracks)`` triggered a lazy
          SELECT every time and two concurrent appends both saw the
          same length. The explicit MAX(position)+1 query inside the
          same transaction (under SQLite's default serializable
          isolation with WAL) gives both callers distinct positions.

        Args:
            playlist_id: ID of playlist
            track_id: ID of track to add
            position: Optional explicit position. If None, the track is
                appended at the next free position. If supplied and
                already present, the track is moved to that position
                via ``reorder_track`` semantics (delete + reinsert).

        Returns:
            True if the playlist now contains the track at the requested
            position (or any position when ``position is None``), False
            on lookup miss or DB failure.
        """
        with self._session_scope() as session:
            try:
                # Verify playlist + track exist BEFORE the insert so FK
                # violations surface as a clean False/log instead of an
                # IntegrityError (which under SQLite is fired at COMMIT
                # rather than at the INSERT statement).
                playlist = session.execute(
                    select(Playlist).where(Playlist.id == playlist_id)
                ).scalars().first()
                track = session.execute(
                    select(Track).where(Track.id == track_id)
                ).scalars().first()

                if not playlist or not track:
                    return False

                # If an explicit position was requested AND the track is
                # already in the playlist at a different position, we need
                # to remove first so the re-INSERT lands at the new spot.
                # If it's already at the requested position (or position is
                # None and the track is present), nothing to do — return
                # True for idempotency.
                current_pos = session.scalar(
                    select(track_playlist.c.position)
                    .where(track_playlist.c.playlist_id == playlist_id)
                    .where(track_playlist.c.track_id == track_id)
                )
                if current_pos is not None:
                    if position is None or current_pos == position:
                        return True
                    # Re-position via atomic DELETE then proceed to INSERT.
                    session.execute(
                        delete(track_playlist)
                        .where(track_playlist.c.playlist_id == playlist_id)
                        .where(track_playlist.c.track_id == track_id)
                    )

                # Resolve target position. When position is None, fold the
                # MAX(position)+1 derivation INTO the INSERT statement via
                # INSERT ... SELECT so SQLite serialises the read and the
                # write as one atomic step. Doing MAX in a separate SELECT
                # leaves a window where two concurrent appends both see the
                # same MAX and INSERT at the same position. INSERT...SELECT
                # under SQLite's WAL writer lock collapses the race.
                if position is None:
                    self._insert_track_at_next_position(session, playlist_id, track_id)
                    # Read back what position we landed at, for the log /
                    # return value (also confirms the insert took effect
                    # vs being ignored by the composite-PK collision).
                    landed_position = session.scalar(
                        select(track_playlist.c.position)
                        .where(track_playlist.c.playlist_id == playlist_id)
                        .where(track_playlist.c.track_id == track_id)
                    )
                    if landed_position is None:
                        # Should not happen — INSERT OR IGNORE either
                        # inserted (we'd find the row) or there was already
                        # a row (current_pos branch above would have
                        # returned True). Log defensively.
                        error(f"add_track: row vanished after INSERT for track {track_id} / playlist {playlist_id}")
                        session.rollback()
                        return False
                    position = int(landed_position)
                else:
                    # Explicit position requested. INSERT OR IGNORE handles
                    # the composite-PK race; the explicit position bypasses
                    # the contiguous-positions invariant intentionally
                    # because the caller asked for a specific slot.
                    stmt = insert(track_playlist).prefix_with('OR IGNORE').values(
                        track_id=track_id,
                        playlist_id=playlist_id,
                        position=position,
                    )
                    session.execute(stmt)

                session.commit()
                debug(
                    f"Added track {track_id} to playlist {playlist.name} "
                    f"at position {position}"
                )
                return True

            except IntegrityError as e:
                # Unexpected — INSERT OR IGNORE shouldn't raise on the
                # uniqueness collision. If it did fire, treat the call as
                # successful (the row is there) but log for visibility.
                session.rollback()
                error(f"Unexpected IntegrityError adding track to playlist: {e}")
                return True
            except Exception as e:
                session.rollback()
                error(f"Failed to add track to playlist: {e}")
                return False

    def add_tracks(self, playlist_id: int, track_ids: list[int]) -> int:
        """Add multiple tracks to a playlist in a single transaction.

        Runs all ``INSERT OR IGNORE ... SELECT COALESCE(MAX(position),-1)+1``
        statements within one session so each insertion sees the previous
        one's position (SQLite read-your-own-writes) and commits once.
        Returns the number of tracks actually inserted (duplicates are silently
        ignored by the ``OR IGNORE`` clause).

        This is the batch equivalent of ``add_track`` used by
        ``POST /api/playlists/{id}/tracks`` to avoid N×to_thread overhead
        for album drag-and-drop and bulk import (fixes #3856).

        Args:
            playlist_id: ID of the target playlist.
            track_ids: Ordered list of track IDs to append.

        Returns:
            Number of new rows inserted (tracks already present are not
            counted).
        """
        if not track_ids:
            return 0

        with self._session_scope() as session:
            try:
                # Verify the playlist exists once rather than per track.
                playlist = session.execute(
                    select(Playlist).where(Playlist.id == playlist_id)
                ).scalars().first()
                if not playlist:
                    return 0

                added = 0
                for track_id in track_ids:
                    # Skip if the track row doesn't exist in the library.
                    if not session.execute(
                        select(Track.id).where(Track.id == track_id)
                    ).scalar_one_or_none():
                        continue

                    # Skip if already in the playlist (idempotent).
                    already_present = session.scalar(
                        select(track_playlist.c.position)
                        .where(track_playlist.c.playlist_id == playlist_id)
                        .where(track_playlist.c.track_id == track_id)
                    )
                    if already_present is not None:
                        continue

                    # Append at next free position.  Because we are inside a
                    # single session, MAX(position) already sees the rows we
                    # inserted for previous track_ids in this loop — SQLite's
                    # read-your-own-writes guarantee closes the position-race
                    # that the per-call version had between sessions.
                    self._insert_track_at_next_position(session, playlist_id, track_id)
                    added += 1

                session.commit()
                debug(
                    f"Batch-added {added}/{len(track_ids)} tracks to playlist {playlist.name}"
                )
                return added

            except Exception as e:
                session.rollback()
                error(f"Failed to batch-add tracks to playlist {playlist_id}: {e}")
                return 0
