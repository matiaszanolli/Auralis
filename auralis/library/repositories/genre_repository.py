"""
Genre Repository
~~~~~~~~~~~~~~~~

Data access layer for genre operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import Any
from collections.abc import Callable

from sqlalchemy.orm import Session, joinedload

from ..models import Genre, Track

logger = logging.getLogger(__name__)


class GenreRepository:
    """Repository for genre database operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.session_factory()

    def get_by_id(self, genre_id: int) -> Genre | None:
        """
        Get genre by ID.

        Args:
            genre_id: Genre ID

        Returns:
            Genre or None if not found
        """
        session = self.get_session()
        try:
            genre = (
                session.query(Genre)
                .filter(Genre.id == genre_id)
                .first()
            )
            if genre:
                session.expunge(genre)
            return genre
        finally:
            session.close()

    def get_by_name(self, name: str) -> Genre | None:
        """
        Get genre by name.

        Args:
            name: Genre name

        Returns:
            Genre or None if not found
        """
        session = self.get_session()
        try:
            genre = (
                session.query(Genre)
                .filter(Genre.name == name)
                .first()
            )
            if genre:
                session.expunge(genre)
            return genre
        finally:
            session.close()

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
        session = self.get_session()
        try:
            # Get total count
            total = session.query(Genre).count()

            # Get genres for current page
            order_column = getattr(Genre, order_by, Genre.name)
            genres = (
                session.query(Genre)
                .order_by(order_column.asc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            # Expunge from session to detach while keeping loaded data
            for genre in genres:
                session.expunge(genre)

            return genres, total
        finally:
            session.close()

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
        session = self.get_session()
        try:
            # Get total count
            genre = session.query(Genre).filter(Genre.id == genre_id).first()
            if not genre:
                return [], 0

            # Get tracks for this genre
            query = (
                session.query(Track)
                .filter(Track.genres.any(Genre.id == genre_id))
                .options(joinedload(Track.album), joinedload(Track.artists))
                .order_by(Track.title)
            )

            total = query.count()
            tracks = query.limit(limit).offset(offset).all()

            # Expunge from session
            for track in tracks:
                session.expunge(track)

            return tracks, total
        finally:
            session.close()

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
        session = self.get_session()
        try:
            genre = Genre(name=name, preferred_profile=preferred_profile)

            # Set additional fields
            for key, value in kwargs.items():
                if hasattr(genre, key) and value is not None:
                    setattr(genre, key, value)

            session.add(genre)
            session.commit()
            session.refresh(genre)
            session.expunge(genre)
            return genre
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create genre: {e}")
            raise
        finally:
            session.close()

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
        session = self.get_session()
        try:
            genre = session.query(Genre).filter(Genre.id == genre_id).first()
            if not genre:
                return None

            # Update only provided fields
            for key, value in fields.items():
                if hasattr(genre, key) and value is not None:
                    setattr(genre, key, value)

            session.commit()
            session.refresh(genre)
            session.expunge(genre)
            return genre
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update genre {genre_id}: {e}")
            raise
        finally:
            session.close()

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
        session = self.get_session()
        try:
            genre = session.query(Genre).filter(Genre.id == genre_id).first()
            if not genre:
                return False

            session.delete(genre)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete genre {genre_id}: {e}")
            raise
        finally:
            session.close()

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
        session = self.get_session()
        try:
            # Search for genres matching the query
            search_filter = Genre.name.ilike(f"%{query}%")
            total = session.query(Genre).filter(search_filter).count()

            genres = (
                session.query(Genre)
                .filter(search_filter)
                .order_by(Genre.name)
                .limit(limit)
                .offset(offset)
                .all()
            )

            # Expunge from session
            for genre in genres:
                session.expunge(genre)

            return genres, total
        finally:
            session.close()
