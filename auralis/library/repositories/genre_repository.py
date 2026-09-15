"""
Genre Repository
~~~~~~~~~~~~~~~~

Data access layer for genre operations

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload, with_expression

from ..models import Genre, Track, track_genre
from .base import BaseRepository, escape_like

logger = logging.getLogger(__name__)


def _track_count_subquery() -> Any:
    """Correlated COUNT of a genre's tracks (#5111).

    Same shape as ArtistRepository's (#5084) and AlbumRepository's (#4777).
    A genre with no tracks yields 0, not NULL, so no COALESCE is needed.
    """
    return (
        select(func.count())
        .select_from(track_genre)
        .where(track_genre.c.genre_id == Genre.id)
        .correlate(Genre)
        .scalar_subquery()
    )


# Every method below expunges the Genre it returns, and Genre.to_dict()
# reports a track count. Detail paths load the collection: without it the lazy
# `tracks` relationship raises DetachedInstanceError on the caller's side
# (#4641). Centralised so a new read path cannot silently omit it — the same
# shape used by album_repository/artist_repository.
_GENRE_LOAD_OPTIONS = (selectinload(Genre.tracks),)

# List paths need only the count, so they read it from a correlated subquery on
# the genre SELECT instead of hydrating every Track row the genre owns (#5111).
_GENRE_LIST_OPTIONS = (with_expression(Genre.track_count_expr, _track_count_subquery()),)


class GenreRepository(BaseRepository):
    """Repository for genre database operations"""

    def get_by_id(self, genre_id: int) -> Genre | None:
        """
        Get genre by ID.

        Args:
            genre_id: Genre ID

        Returns:
            Genre or None if not found
        """
        with self._session_scope() as session:
            genre = session.execute(
                select(Genre).where(Genre.id == genre_id).options(*_GENRE_LOAD_OPTIONS)
            ).scalars().first()
            if genre:
                session.expunge(genre)
            return genre

    def get_by_name(self, name: str) -> Genre | None:
        """
        Get genre by name.

        Args:
            name: Genre name

        Returns:
            Genre or None if not found
        """
        with self._session_scope() as session:
            genre = session.execute(
                select(Genre).where(Genre.name == name).options(*_GENRE_LOAD_OPTIONS)
            ).scalars().first()
            if genre:
                session.expunge(genre)
            return genre

    def get_all(self, limit: int = 50, offset: int = 0, order_by: str = 'name') -> tuple[list[Genre], int]:
        """
        Get all genres with pagination.

        Args:
            limit: Maximum number of genres to return
            offset: Number of genres to skip
            order_by: Column to order by ('name', 'created_at')

        Returns:
            Tuple of (genres list, total count)
        """
        with self._session_scope() as session:
            # Get total count
            total = session.execute(
                select(func.count()).select_from(Genre)
            ).scalar_one()

            # Get genres for current page (whitelist to prevent arbitrary attribute access)
            VALID_ORDER_COLUMNS = {'name', 'created_at'}
            if order_by not in VALID_ORDER_COLUMNS:
                order_by = 'name'
            order_column = getattr(Genre, order_by, Genre.name)
            genres = session.execute(
                select(Genre)
                .options(*_GENRE_LIST_OPTIONS)
                .order_by(order_column.asc())
                .limit(limit)
                .offset(offset)
            ).scalars().all()

            # Expunge from session to detach while keeping loaded data
            for genre in genres:
                session.expunge(genre)

            return list(genres), total

    def get_tracks_by_genre(
        self,
        genre_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[list[Track], int]:
        """
        Get all tracks for a genre with pagination.

        Args:
            genre_id: Genre ID
            limit: Maximum number of tracks to return
            offset: Number of tracks to skip

        Returns:
            Tuple of (tracks list, total count)
        """
        with self._session_scope() as session:
            # Get total count
            genre = session.execute(
                select(Genre).where(Genre.id == genre_id)
            ).scalars().first()
            if not genre:
                return [], 0

            # Get tracks for this genre
            track_filter = Track.genres.any(Genre.id == genre_id)

            total = session.execute(
                select(func.count()).select_from(Track).where(track_filter)
            ).scalar_one()

            tracks = session.execute(
                select(Track)
                .where(track_filter)
                .options(joinedload(Track.album), joinedload(Track.artists))
                .order_by(Track.title)
                .limit(limit)
                .offset(offset)
            ).scalars().unique().all()

            # Expunge from session
            for track in tracks:
                session.expunge(track)

            return list(tracks), total

    def create(self, name: str, preferred_profile: str | None = None, **kwargs: Any) -> Genre:
        """
        Create a new genre.

        Args:
            name: Genre name
            preferred_profile: Preferred mastering profile
            **kwargs: Additional genre fields

        Returns:
            Created genre

        Raises:
            Exception: If genre creation fails (e.g., duplicate name)
        """
        with self._session_scope() as session:
            try:
                genre = Genre(name=name, preferred_profile=preferred_profile)

                # Set additional fields
                for key, value in kwargs.items():
                    if hasattr(genre, key) and value is not None:
                        setattr(genre, key, value)

                session.add(genre)
                session.commit()
                session.refresh(genre)
                # refresh() expires the instance but does not re-apply the
                # query-level load options, so force the relationship in while
                # still attached (#4641).
                _ = genre.tracks
                session.expunge(genre)
                return genre
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to create genre: {e}")
                raise

    def update(self, genre_id: int, **fields: Any) -> Genre | None:
        """
        Update genre fields.

        Args:
            genre_id: Genre ID
            **fields: Fields to update (only non-None values)

        Returns:
            Updated genre or None if not found

        Raises:
            Exception: If update fails
        """
        with self._session_scope() as session:
            try:
                genre = session.execute(
                    select(Genre).where(Genre.id == genre_id)
                ).scalars().first()
                if not genre:
                    return None

                # Update only provided fields
                for key, value in fields.items():
                    if hasattr(genre, key) and value is not None:
                        setattr(genre, key, value)

                session.commit()
                session.refresh(genre)
                _ = genre.tracks  # force-load before detaching (#4641)
                session.expunge(genre)
                return genre
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update genre {genre_id}: {e}")
                raise

    def delete(self, genre_id: int) -> bool:
        """
        Delete a genre by ID.

        Args:
            genre_id: Genre ID

        Returns:
            True if deleted, False if not found

        Raises:
            Exception: If deletion fails
        """
        with self._session_scope() as session:
            try:
                genre = session.execute(
                    select(Genre).where(Genre.id == genre_id)
                ).scalars().first()
                if not genre:
                    return False

                session.delete(genre)
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to delete genre {genre_id}: {e}")
                raise

    def search(self, query: str, limit: int = 50, offset: int = 0) -> tuple[list[Genre], int]:
        """
        Search genres by name.

        Args:
            query: Search query (case-insensitive substring match)
            limit: Maximum number of genres to return
            offset: Number of genres to skip

        Returns:
            Tuple of (genres list, total count)
        """
        with self._session_scope() as session:
            # Search for genres matching the query.
            # Escape LIKE metacharacters to prevent full-table scans on '%'/'_' (fixes #2405).
            escaped = escape_like(query)
            search_filter = Genre.name.ilike(f"%{escaped}%", escape='\\')
            total = session.execute(
                select(func.count()).select_from(Genre).where(search_filter)
            ).scalar_one()

            genres = session.execute(
                select(Genre)
                .where(search_filter)
                .options(*_GENRE_LIST_OPTIONS)
                .order_by(Genre.name)
                .limit(limit)
                .offset(offset)
            ).scalars().all()

            # Expunge from session
            for genre in genres:
                session.expunge(genre)

            return list(genres), total
