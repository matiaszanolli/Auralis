"""
Playlist Repository
~~~~~~~~~~~~~~~~~~

Data access layer for playlist operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any
from collections.abc import Callable

from sqlalchemy import and_, delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from ..models.base import track_playlist
from sqlalchemy.orm import Session, selectinload

from ...utils.logging import debug, error, info
from ..models import Playlist, Track


class PlaylistRepository:
    """Repository for playlist database operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """
        Initialize playlist repository

        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def create(self, name: str, description: str = "", track_ids: list[int] | None = None) -> Playlist | None:
        """
        Create a new playlist

        Args:
            name: Playlist name
            description: Playlist description
            track_ids: List of track IDs to add

        Returns:
            Playlist object if successful
        """
        session = self.get_session()
        try:
            playlist = Playlist(name=name, description=description)
            session.add(playlist)
            session.flush()  # Flush to get the ID without committing yet
            playlist_id = playlist.id  # Capture ID before expunging

            # #3731: explicit-position bulk insert. The prior implementation
            # did `playlist.tracks = tracks`, which generated an INSERT per
            # row with no `position` value, so SQLAlchemy applied the
            # column default (0) to every row — `reorder_track` then
            # silently no-op'd on the freshly-created playlist because its
            # `position > from_index` WHERE clauses matched nothing.
            #
            # Resolving the track ids inside a single SELECT keeps unknown
            # ids out of the INSERT; enumerating the caller-supplied
            # `track_ids` order in Python gives deterministic positions
            # 0..N-1 matching the caller's intent. Duplicates in the input
            # are collapsed (first occurrence wins) — the composite PK
            # would reject them anyway.
            if track_ids:
                existing_ids = set(
                    session.execute(
                        select(Track.id).where(Track.id.in_(track_ids))
                    ).scalars().all()
                )
                rows: list[dict[str, Any]] = []
                seen: set[int] = set()
                position = 0
                for tid in track_ids:
                    if tid in seen or tid not in existing_ids:
                        continue
                    seen.add(tid)
                    rows.append({
                        "playlist_id": playlist_id,
                        "track_id": tid,
                        "position": position,
                    })
                    position += 1
                if rows:
                    session.execute(insert(track_playlist), rows)

            session.commit()

            # Refresh playlist and eager-load tracks to avoid DetachedInstanceError
            session.refresh(playlist)
            # Access tracks to ensure they're loaded before session closes
            _ = playlist.tracks

            session.expunge(playlist)
            info(f"Created playlist: {name}")
            return playlist

        except Exception as e:
            session.rollback()
            error(f"Failed to create playlist: {e}")
            return None
        finally:
            session.close()

    def get_by_id(self, playlist_id: int) -> Playlist | None:
        """Get playlist by ID with eager loading"""
        session = self.get_session()
        try:
            playlist = session.execute(
                select(Playlist).options(
                    selectinload(Playlist.tracks).selectinload(Track.artists),
                    selectinload(Playlist.tracks).selectinload(Track.genres),
                    selectinload(Playlist.tracks).selectinload(Track.album)
                ).where(Playlist.id == playlist_id)
            ).scalars().first()

            if playlist:
                session.expunge(playlist)
            return playlist
        finally:
            session.close()

    def get_all(self) -> list[Playlist]:
        """Get all playlists with eager loading"""
        session = self.get_session()
        try:
            playlists = session.execute(
                select(Playlist)
                .options(selectinload(Playlist.tracks))
                .order_by(Playlist.name)
            ).scalars().all()
            # #3709: expunge_all() detaches the playlists AND their nested
            # Track objects from the session. The previous per-playlist
            # `session.expunge(playlist)` only detached the parent; nested
            # tracks remained tied to the about-to-close session, so any
            # downstream access to `track.artists` / `track.album` (not
            # pre-loaded here) raised DetachedInstanceError.
            session.expunge_all()
            return list(playlists)
        finally:
            session.close()

    def update(self, playlist_id: int, update_data: dict[str, Any]) -> bool:
        """
        Update playlist

        Args:
            playlist_id: ID of playlist to update
            update_data: Dictionary with fields to update

        Returns:
            True if successful, False otherwise
        """
        session = self.get_session()
        try:
            playlist = session.execute(select(Playlist).where(Playlist.id == playlist_id)).scalars().first()
            if not playlist:
                return False

            # Update allowed fields
            for key in ['name', 'description']:
                if key in update_data:
                    setattr(playlist, key, update_data[key])

            session.commit()
            info(f"Updated playlist: {playlist.name}")
            return True

        except Exception as e:
            session.rollback()
            error(f"Failed to update playlist: {e}")
            return False
        finally:
            session.close()

    def delete(self, playlist_id: int) -> bool:
        """
        Delete playlist

        Args:
            playlist_id: ID of playlist to delete

        Returns:
            True if successful, False otherwise
        """
        session = self.get_session()
        try:
            playlist = session.execute(select(Playlist).where(Playlist.id == playlist_id)).scalars().first()
            if not playlist:
                return False

            session.delete(playlist)
            session.commit()
            info(f"Deleted playlist: {playlist.name}")
            return True

        except Exception as e:
            session.rollback()
            error(f"Failed to delete playlist: {e}")
            return False
        finally:
            session.close()

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
        session = self.get_session()
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
                # text() form is needed because SQLAlchemy Core's
                # insert().from_select() doesn't pass through OR IGNORE
                # cleanly with bound parameters in a way SQLite likes.
                # Inline scalars + SQL functions for portability.
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
        finally:
            session.close()

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
