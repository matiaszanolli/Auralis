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
:license: GPLv3, see LICENSE for more details.
"""

from collections.abc import Callable

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from ...utils.logging import debug, error, info
from ..models import Playlist
from ..models.base import track_playlist


class PlaylistOrderingMixin:
    """Remove/clear/reorder operations, sharing the repository's session factory.

    ``get_session`` is provided by ``BaseRepository`` — declared here bare
    (no assignment) so type checkers know this mixin depends on it without
    shadowing the real implementation via MRO.
    """

    get_session: Callable[[], Session]

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
        session = self.get_session()
        try:
            # Capture the deleted row's position first; we need it for
            # the position-shift UPDATE below.
            removed_position = session.scalar(
                select(track_playlist.c.position)
                .where(track_playlist.c.playlist_id == playlist_id)
                .where(track_playlist.c.track_id == track_id)
            )

            result = session.execute(
                delete(track_playlist).where(
                    and_(
                        track_playlist.c.playlist_id == playlist_id,
                        track_playlist.c.track_id == track_id,
                    )
                )
            )

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

        except Exception as e:
            session.rollback()
            error(f"Failed to remove track from playlist: {e}")
            return False
        finally:
            session.close()

    def clear(self, playlist_id: int) -> bool:
        """Remove all tracks from playlist"""
        session = self.get_session()
        try:
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

        except Exception as e:
            session.rollback()
            error(f"Failed to clear playlist: {e}")
            return False
        finally:
            session.close()

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

        session = self.get_session()
        try:
            # Resolve the moving track + the playlist size in one go.
            moving_track_id = session.scalar(
                select(track_playlist.c.track_id)
                .where(track_playlist.c.playlist_id == playlist_id)
                .where(track_playlist.c.position == from_index)
            )
            if moving_track_id is None:
                error(f"Invalid from_index: {from_index} (no row in playlist {playlist_id})")
                return False

            size = session.scalar(
                select(func.count()).select_from(track_playlist)
                .where(track_playlist.c.playlist_id == playlist_id)
            ) or 0
            if not (0 <= to_index < size):
                error(f"Invalid to_index: {to_index} (playlist size {size})")
                return False

            # Move the row OUT of the way (sentinel position = -1) so
            # the shift UPDATE below doesn't trip the unique
            # constraint with its own row mid-rewrite.
            session.execute(
                update(track_playlist)
                .where(track_playlist.c.playlist_id == playlist_id)
                .where(track_playlist.c.track_id == moving_track_id)
                .values(position=-1)
            )

            if to_index > from_index:
                # Shift the rows in (from_index, to_index] down by 1.
                session.execute(
                    update(track_playlist)
                    .where(track_playlist.c.playlist_id == playlist_id)
                    .where(track_playlist.c.position > from_index)
                    .where(track_playlist.c.position <= to_index)
                    .values(position=track_playlist.c.position - 1)
                )
            else:
                # Shift the rows in [to_index, from_index) up by 1.
                session.execute(
                    update(track_playlist)
                    .where(track_playlist.c.playlist_id == playlist_id)
                    .where(track_playlist.c.position >= to_index)
                    .where(track_playlist.c.position < from_index)
                    .values(position=track_playlist.c.position + 1)
                )

            # Slot the moving row into its target position.
            session.execute(
                update(track_playlist)
                .where(track_playlist.c.playlist_id == playlist_id)
                .where(track_playlist.c.track_id == moving_track_id)
                .values(position=to_index)
            )

            session.commit()
            debug(
                f"Reordered track {moving_track_id} in playlist {playlist_id} "
                f"from {from_index} to {to_index}"
            )
            return True

        except Exception as e:
            session.rollback()
            error(f"Failed to reorder track in playlist: {e}")
            return False
        finally:
            session.close()
