"""
Album Repository
~~~~~~~~~~~~~~~

Data access layer for album operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pathlib import Path
from collections.abc import Callable

from sqlalchemy.orm import Session, joinedload, selectinload

from ..artwork import create_artwork_extractor
from ..models import Album


class AlbumRepository:
    """Repository for album database operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

        # Initialize artwork extractor
        artwork_dir = Path.home() / ".auralis" / "artwork"
        self.artwork_extractor = create_artwork_extractor(str(artwork_dir))

    def get_session(self) -> Session:
        return self.session_factory()

    def get_by_id(self, album_id: int) -> Album | None:
        """Get album by ID with relationships loaded"""
        session = self.get_session()
        try:
            album = (
                session.query(Album)
                .options(joinedload(Album.artist), selectinload(Album.tracks))
                .filter(Album.id == album_id)
                .first()
            )
            if album:
                # Expunge the album AND all eagerly-loaded related objects so
                # callers can access album.tracks after the session closes
                # without hitting DetachedInstanceError (fixes #2406).
                session.expunge_all()
            return album
        finally:
            session.close()

    def get_by_title(self, title: str) -> Album | None:
        """Get album by title with relationships loaded"""
        session = self.get_session()
        try:
            album = (
                session.query(Album)
                .options(joinedload(Album.artist), selectinload(Album.tracks))
                .filter(Album.title == title)
                .first()
            )
            if album:
                session.expunge(album)
            return album
        finally:
            session.close()

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
        session = self.get_session()
        try:
            # Get total count
            total = session.query(Album).count()

            # Get albums for current page (whitelist to prevent arbitrary attribute access)
            VALID_ORDER_COLUMNS = {'title', 'year', 'created_at'}
            if order_by not in VALID_ORDER_COLUMNS:
                order_by = 'title'
            order_column = getattr(Album, order_by, Album.title)
            albums = (
                session.query(Album)
                .options(joinedload(Album.artist), selectinload(Album.tracks))
                .order_by(order_column.asc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            for album in albums:
                session.expunge(album)

            return albums, total
        finally:
            session.close()

    def get_recent(self, limit: int = 50, offset: int = 0) -> list[Album]:
        """Get recently added albums with pagination"""
        session = self.get_session()
        try:
            albums = (
                session.query(Album)
                .options(joinedload(Album.artist), selectinload(Album.tracks))
                .order_by(Album.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            for album in albums:
                session.expunge(album)
            return albums
        finally:
            session.close()

    def search(self, query: str, limit: int = 50, offset: int = 0) -> tuple[list[Album], int]:
        """
        Search albums by title or artist name

        Args:
            query: Search query string
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (matching albums, total match count) — total enables correct
            pagination (fixes #2482: estimated total was always wrong).
        """
        session = self.get_session()
        try:
            from sqlalchemy import func, or_

            from ..models import Artist

            # Escape LIKE metacharacters so a query containing '%' or '_' does
            # not accidentally match all rows (fixes #2405).
            escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            search_term = f"%{escaped}%"
            base_query = (
                session.query(Album)
                .join(Album.artist, isouter=True)
                .filter(
                    or_(
                        Album.title.ilike(search_term),
                        Artist.name.ilike(search_term)
                    )
                )
            )

            total = base_query.with_entities(func.count(Album.id)).scalar() or 0

            results = (
                base_query
                .options(selectinload(Album.artist), selectinload(Album.tracks))
                .limit(limit)
                .offset(offset)
                .all()
            )

            for album in results:
                session.expunge(album)
            return results, total
        finally:
            session.close()

    def extract_and_save_artwork(self, album_id: int) -> str | None:
        """
        Extract artwork from album's tracks and save it

        Args:
            album_id: Album ID to extract artwork for

        Returns:
            Path to saved artwork, or None if extraction failed
        """
        session = self.get_session()
        try:
            album = (
                session.query(Album)
                .options(selectinload(Album.tracks))
                .filter(Album.id == album_id)
                .first()
            )

            if not album or not album.tracks:
                return None

            # Try to extract artwork from the first track
            for track in album.tracks:
                if track.filepath and Path(track.filepath).exists():
                    artwork_path = self.artwork_extractor.extract_artwork(
                        track.filepath, album_id
                    )

                    if artwork_path:
                        # Update album with artwork path
                        album.artwork_path = artwork_path  # type: ignore[assignment]
                        session.commit()
                        session.refresh(album)
                        return artwork_path

            return None

        finally:
            session.close()

    def update_artwork(self, album_id: int, artwork_path: str) -> bool:
        """
        Update album artwork path

        Args:
            album_id: Album ID
            artwork_path: Path to artwork file

        Returns:
            True if updated successfully
        """
        session = self.get_session()
        try:
            album = session.query(Album).filter(Album.id == album_id).first()
            if album:
                album.artwork_path = artwork_path  # type: ignore[assignment]
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()  # fixes #2238: prevent dirty session in pool
            raise
        finally:
            session.close()

    def delete_artwork(self, album_id: int) -> bool:
        """
        Delete album artwork

        Args:
            album_id: Album ID

        Returns:
            True if deleted successfully
        """
        session = self.get_session()
        try:
            album = session.query(Album).filter(Album.id == album_id).first()
            if album and album.artwork_path:
                # Delete file
                self.artwork_extractor.delete_artwork(album.artwork_path)  # type: ignore[arg-type]
                # Clear database reference
                album.artwork_path = None  # type: ignore[assignment]
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()  # fixes #2238: prevent dirty session in pool
            raise
        finally:
            session.close()

    def update_artwork_path(self, album_id: int, artwork_path: str) -> Album | None:
        """
        Update album artwork path.

        Args:
            album_id: Album ID
            artwork_path: Path to artwork file

        Returns:
            Updated album or None if not found

        Raises:
            Exception: If update fails
        """
        session = self.get_session()
        try:
            album = session.query(Album).filter(Album.id == album_id).first()
            if not album:
                return None

            album.artwork_path = artwork_path  # type: ignore[assignment]
            session.commit()
            session.refresh(album)
            session.expunge(album)
            return album
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
