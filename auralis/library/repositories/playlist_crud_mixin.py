"""
Playlist CRUD Mixin
~~~~~~~~~~~~~~~~~~~

Single-playlist create/read/update/delete for ``PlaylistRepository``,
extracted from ``playlist_repository.py`` (#4511) to stay under the
project's 300-line convention. Pairs with ``playlist_query_mixin.py``
(listing/search) and ``playlist_membership_mixin.py`` /
``playlist_ordering_mixin.py`` (track membership and position management)
— all four are always mixed into ``PlaylistRepository`` together.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session, selectinload

from ...utils.logging import error, info
from ..models import Playlist, Track
from ..models.base import track_playlist


class PlaylistCrudMixin:
    """Single-playlist create/get/update/delete, sharing the repository's session factory.

    ``get_session`` is provided by ``BaseRepository`` — declared here bare
    (no assignment) so type checkers know this mixin depends on it without
    shadowing the real implementation via MRO.
    """

    get_session: Callable[[], Session]

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
