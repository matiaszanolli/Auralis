"""
Album Repository
~~~~~~~~~~~~~~~

Data access layer for album operations

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload, with_expression

from ..artwork import create_artwork_extractor
from ..data_dir import artwork_dir
from ..models import Album, Artist, Track
from .album_artwork import AlbumArtworkMixin
from .base import correlated_count, correlated_sum, escape_like


def _total_duration_subquery() -> Any:
    """Correlated SUM of an album's track durations — base.correlated_sum
    (the direct-FK shape), one builder shared with playlists (#6212)."""
    return correlated_sum(Track, Track.duration, Track.album_id, Album)


# Named eager-load constants (#5028), mirroring track_repository.py's
# _track_eager_options() / genre_repository.py's _GENRE_LOAD_OPTIONS
# convention. #4236 fixed a DetachedInstanceError caused by exactly this
# duplication (one method's inline tuple fixed, its sibling's copy left
# stale) and its own proposed fix recommended this extraction — done here so
# a future read path can't silently omit it again.

# Single-album detail reads: get_by_id hands the album straight
# to to_dict(), which reads both album.artist and album.tracks.
#
# Track relationships used by Track.to_dict() are eager-loaded too
# (#5170/#5260). Everything here is expunged before it is returned, so a lazy
# relationship access downstream otherwise degrades to an empty wire value.
_ALBUM_DETAIL_OPTIONS = (
    joinedload(Album.artist),
    selectinload(Album.tracks).selectinload(Track.genres),
    selectinload(Album.tracks).selectinload(Track.artists),
    selectinload(Album.tracks).joinedload(Track.album),
)

# Paginated/listing reads: track_count_expr/total_duration_expr cover what
# the list serializer needs — no eager Album.tracks (fixes #4777's N+1).
_ALBUM_LIST_OPTIONS = (
    joinedload(Album.artist),
    with_expression(Album.track_count_expr, correlated_count(Track, Track.album_id, Album)),
    with_expression(Album.total_duration_expr, _total_duration_subquery()),
)


class AlbumRepository(AlbumArtworkMixin):
    """Repository for album database operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        super().__init__(session_factory)

        # Initialize artwork extractor
        self.artwork_extractor = create_artwork_extractor(str(artwork_dir()))

    def get_by_id(self, album_id: int) -> Album | None:
        """Get album by ID with relationships loaded"""
        with self._session_scope() as session:
            album = self._first_detached(
                session,
                select(Album)
                .options(*_ALBUM_DETAIL_OPTIONS)
                .where(Album.id == album_id),
            )
            return album

    def get_all(self, limit: int = 50, offset: int = 0, order_by: str = 'title') -> tuple[list[Album], int]:
        """
        Get all albums with pagination and total count

        Args:
            limit: Maximum number of albums to return
            offset: Number of albums to skip
            order_by: Column to order by ('title', 'year', 'created_at')

        Returns:
            Tuple of (albums list, total count)
        """
        with self._session_scope() as session:
            # Get total count
            total = session.execute(
                select(func.count()).select_from(Album)
            ).scalar_one()

            # Get albums for current page (whitelist to prevent arbitrary attribute access)
            VALID_ORDER_COLUMNS = {'title', 'year', 'created_at'}
            if order_by not in VALID_ORDER_COLUMNS:
                order_by = 'title'
            order_column = getattr(Album, order_by, Album.title)
            albums = self._all_detached(
                session,
                select(Album)
                .options(*_ALBUM_LIST_OPTIONS)
                .order_by(order_column.asc(), Album.id.asc())
                .limit(limit)
                .offset(offset),
            )

            # Expunge every album AND its eagerly-loaded artist (fixes #2406 /
            # #4236 — a per-item expunge(album) does not cascade to related
            # objects, leaving them DetachedInstanceError-prone). tracks is no
            # longer eager-loaded here (#4777) — track_count_expr/
            # total_duration_expr cover what the serializer actually needs.

            return albums, total

    def get_recent(self, limit: int = 50, offset: int = 0) -> list[Album]:
        """Get recently added albums with pagination"""
        with self._session_scope() as session:
            albums = self._all_detached(
                session,
                select(Album)
                .options(*_ALBUM_LIST_OPTIONS)
                .order_by(Album.created_at.desc(), Album.id.desc())
                .limit(limit)
                .offset(offset),
            )
            return albums

    def search(self, query: str, limit: int = 50, offset: int = 0, order_by: str = 'title') -> tuple[list[Album], int]:
        """
        Search albums by title or artist name

        Args:
            query: Search query string
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: Column to order by ('title', 'year', 'created_at')

        Returns:
            Tuple of (matching albums, total match count) — total enables correct
            pagination (fixes #2482: estimated total was always wrong).
        """
        with self._session_scope() as session:
            # Escape LIKE metacharacters so a query containing '%' or '_' does
            # not accidentally match all rows (fixes #2405).
            escaped = escape_like(query)
            search_term = f"%{escaped}%"
            search_filter = or_(
                Album.title.ilike(search_term, escape='\\'),
                Artist.name.ilike(search_term, escape='\\')
            )

            total = session.execute(
                select(func.count(Album.id))
                .join(Album.artist, isouter=True)
                .where(search_filter)
            ).scalar_one_or_none() or 0

            # Whitelist order_by to prevent arbitrary attribute access
            VALID_ORDER_COLUMNS = {'title', 'year', 'created_at'}
            if order_by not in VALID_ORDER_COLUMNS:
                order_by = 'title'
            order_column = getattr(Album, order_by, Album.title)

            results = self._all_detached(
                session,
                select(Album)
                .join(Album.artist, isouter=True)
                .where(search_filter)
                # Deliberately not _ALBUM_LIST_OPTIONS (#5028 CONSISTENCY check):
                # this query already JOINs Album.artist explicitly for the WHERE
                # filter above, so joinedload(Album.artist) on the same
                # relationship would attach a second, conflicting join.
                # selectinload sidesteps that with its own separate query — the
                # other two expressions are identical to _ALBUM_LIST_OPTIONS.
                .options(
                    selectinload(Album.artist),
                    with_expression(Album.track_count_expr, correlated_count(Track, Track.album_id, Album)),
                    with_expression(Album.total_duration_expr, _total_duration_subquery()),
                )
                .order_by(order_column.asc(), Album.id.asc())
                .limit(limit)
                .offset(offset),
            )

            return results, total
