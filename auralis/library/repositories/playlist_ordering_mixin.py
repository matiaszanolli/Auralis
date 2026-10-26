"""
Playlist Ordering Mixin
~~~~~~~~~~~~~~~~~~~~~~~

Removing and reordering tracks within a playlist for
``PlaylistRepository``, extracted from ``playlist_repository.py`` (#4511)
to stay under the project's 300-line convention. Pairs with
``playlist_membership_mixin.py`` (adding tracks) — together they cover
track membership and position management — and with
``playlist_crud_mixin.py`` / ``playlist_query_mixin.py`` (single-playlist
CRUD and listing/search). All four are always mixed into
``PlaylistRepository`` together.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, cast

from sqlalchemy import CursorResult, and_, delete, select, update
from sqlalchemy.orm import selectinload

from ...utils.logging import debug, error, info
from ..models import Playlist
from ..models.base import track_playlist
from .base import BaseRepository


class PlaylistOrderingMixin(BaseRepository):
    """Remove/clear/reorder operations, sharing the repository's session factory.

    Inherits ``BaseRepository`` directly for ``get_session``/
    ``_session_scope`` (#4604) — see ``playlist_membership_mixin.py`` for
    why a bare annotation doesn't work for ``_session_scope`` here.
    """

    def remove_track(self, playlist_id: int, track_id: int) -> bool:
        """Remove a track from a playlist.

        Issues a single atomic DELETE on the ``track_playlist`` association
        table. No lazy-load of the full collection, no read→modify→commit
        window, and naturally idempotent under concurrent calls — the
        previous load-then-mutate implementation had a race window between
        the lazy SELECT and the COMMIT where two threads could collide on
        the same playlist (#3340).

        #3725: also compacts positions after a successful delete so the
        per-playlist invariant ``positions are contiguous 0..N-1``
        holds. Without compaction, reorder_track's index validation
        becomes ambiguous and add_track's MAX+1 path leaves gaps.
        """
        with self._guarded("Failed to remove track from playlist") as session:
            # Capture the deleted row's position first; we need it for
            # the position-shift UPDATE below.
            removed_position = session.scalar(
                select(track_playlist.c.position)
                .where(track_playlist.c.playlist_id == playlist_id)
                .where(track_playlist.c.track_id == track_id)
            )

            # cast(): session.execute() is typed Result, which has no
            # rowcount; a DELETE really returns a CursorResult.
            result = cast(CursorResult[Any], session.execute(
                delete(track_playlist).where(
                    and_(
                        track_playlist.c.playlist_id == playlist_id,
                        track_playlist.c.track_id == track_id,
                    )
                )
            ))

            if removed_position is not None and result.rowcount:
                # Compact the trailing positions so we stay contiguous.
                session.execute(
                    update(track_playlist)
                    .where(track_playlist.c.playlist_id == playlist_id)
                    .where(track_playlist.c.position > removed_position)
                    .values(position=track_playlist.c.position - 1)
                )

            session.commit()
            if result.rowcount:
                debug(f"Removed track {track_id} from playlist {playlist_id}")
            return True
        return False

    def clear(self, playlist_id: int) -> bool:
        """Remove all tracks from playlist"""
        with self._guarded("Failed to clear playlist") as session:
            # #3707: eager-load tracks so `playlist.tracks = []` doesn't
            # trigger an implicit lazy SELECT first.
            playlist = session.execute(
                select(Playlist)
                .options(selectinload(Playlist.tracks))
                .where(Playlist.id == playlist_id)
            ).scalars().first()
            if not playlist:
                return False

            playlist.tracks = []
            session.commit()
            info(f"Cleared playlist: {playlist.name}")
            return True
        return False

    def reorder_track(self, playlist_id: int, from_index: int, to_index: int) -> bool:
        """Reorder a track within a playlist.

        #3725: operates directly on the explicit ``position`` column
        instead of mutating the ORM-loaded ``playlist.tracks`` list and
        relying on SQLAlchemy to rewrite the association rows. The
        previous pop+insert pattern's per-position rewrites were not
        atomic — a concurrent ``add_track`` could land between the pop
        and the insert and shift positions out from under us.

        The new implementation issues three UPDATE statements inside a
        single transaction:
          1. SELECT the moving row's track_id (and validate indices).
          2. Shift everything between from_index and to_index by ±1.
          3. UPDATE the moving row to to_index.
        This keeps the per-playlist position invariant
        (contiguous 0..N-1, no gaps, no duplicates) under concurrent
        traffic — SQLite serializes writes within a transaction.

        Args:
            playlist_id: ID of playlist.
            from_index: Current position of the track (0-based).
            to_index: Target position of the track (0-based).

        Returns:
            True if the row was successfully repositioned, False on
            lookup miss or out-of-range index.
        """
        if from_index == to_index:
            return True

        with self._guarded("Failed to reorder track in playlist") as session:
            # #5581/#5573: resolve rows by LOGICAL index in position
            # order instead of matching position == from_index exactly.
            # Writers now keep positions contiguous, but playlists
            # written before that fix can carry gaps
            # (e.g. (A,0),(C,2) after a library delete), which made
            # from_index lookups miss and left playlists un-reorderable.
            ordered_track_ids = list(session.execute(
                select(track_playlist.c.track_id)
                .where(track_playlist.c.playlist_id == playlist_id)
                .order_by(track_playlist.c.position, track_playlist.c.track_id)
            ).scalars().all())

            size = len(ordered_track_ids)
            if not (0 <= from_index < size):
                error(f"Invalid from_index: {from_index} (playlist size {size})")
                return False
            if not (0 <= to_index < size):
                error(f"Invalid to_index: {to_index} (playlist size {size})")
                return False

            moving_track_id = ordered_track_ids[from_index]
            # Pop the mover from the logical order and re-insert at the
            # target slot; the resulting order is written back as
            # contiguous positions 0..N-1 (also healing legacy gaps).
            ordered_track_ids.insert(to_index, ordered_track_ids.pop(from_index))

            for new_position, track_id in enumerate(ordered_track_ids):
                session.execute(
                    update(track_playlist)
                    .where(track_playlist.c.playlist_id == playlist_id)
                    .where(track_playlist.c.track_id == track_id)
                    .values(position=new_position)
                )

            session.commit()
            debug(
                f"Reordered track {moving_track_id} in playlist {playlist_id} "
                f"from {from_index} to {to_index}"
            )
            return True
        return False
