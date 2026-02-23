"""
Artist Repository
~~~~~~~~~~~~~~~~

Data access layer for artist operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from collections.abc import Callable

from sqlalchemy.orm import Session, joinedload, selectinload

from ..models import Album, Artist, Track


class ArtistRepository:
    """Repository for artist database operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get_session(self) -> Session:
        return self.session_factory()

    def get_by_id(self, artist_id: int) -> Artist | None:
        """Get artist by ID with relationships loaded"""
        session = self.get_session()
        try:
            artist = (
                session.query(Artist)
                .options(
                    joinedload(Artist.tracks).joinedload(Track.genres),
                    joinedload(Artist.albums).joinedload(Album.tracks)
                )
                .filter(Artist.id == artist_id)
                .first()
            )
            if artist:
                session.expunge(artist)
            return artist
        finally:
            session.close()

    def get_by_name(self, name: str) -> Artist | None:
        """Get artist by name with relationships loaded"""
        session = self.get_session()
        try:
            artist = (
                session.query(Artist)
                .options(
                    joinedload(Artist.tracks).joinedload(Track.genres),
                    joinedload(Artist.albums)
                )
                .filter(Artist.name == name)
                .first()
            )
            if artist:
                session.expunge(artist)
            return artist
        finally:
            session.close()

    def get_all(self, limit: int = 50, offset: int = 0, order_by: str = 'name') -> tuple[list[Artist], int]:
        """Get all artists with pagination and relationships loaded

        Args:
            limit: Maximum number of artists to return
            offset: Number of artists to skip
            order_by: Field to sort by ('name', 'album_count', 'track_count')

        Returns:
            Tuple of (artists list, total count)
        """
        session = self.get_session()
        try:
            from sqlalchemy import desc, func

            # Get total count
            total = session.query(Artist).count()

            # Determine sort column
            if order_by == 'album_count':
                # Subquery to count albums per artist
                album_count_query = (
                    session.query(Artist.id, func.count(Artist.albums).label('album_count'))
                    .join(Artist.albums)
                    .group_by(Artist.id)
                    .subquery()
                )
                order_column = desc(album_count_query.c.album_count)
            elif order_by == 'track_count':
                # Subquery to count tracks per artist
                track_count_query = (
                    session.query(Artist.id, func.count(Artist.tracks).label('track_count'))
                    .join(Artist.tracks)
                    .group_by(Artist.id)
                    .subquery()
                )
                order_column = desc(track_count_query.c.track_count)
            else:  # Default to name
                order_column = Artist.name.asc()

            # Get paginated artists with all relationships eagerly loaded.
            # Use selectinload (separate IN queries) instead of nested joinedload
            # to avoid the N×M Cartesian-product row explosion (fixes #2516).
            artists = (
                session.query(Artist)
                .options(
                    selectinload(Artist.tracks).selectinload(Track.genres),
                    selectinload(Artist.albums)
                )
                .order_by(order_column)
                .limit(limit)
                .offset(offset)
                .all()
            )

            for artist in artists:
                session.expunge(artist)
            return artists, total
        finally:
            session.close()

    def search(self, query: str, limit: int = 50, offset: int = 0) -> tuple[list[Artist], int]:
        """Search artists by name with pagination

        Args:
            query: Search string to match against artist name
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (artists list, total count of matching artists)
        """
        session = self.get_session()
        try:
            # Escape LIKE metacharacters so a query containing '%' or '_' does
            # not accidentally match all rows (fixes #2405).
            escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            search_term = f"%{escaped}%"

            # Get total count of matching artists
            total = (
                session.query(Artist)
                .filter(Artist.name.ilike(search_term))
                .count()
            )

            # Get paginated results.
            # Use selectinload (separate IN queries) instead of nested joinedload
            # to avoid the N×M Cartesian-product row explosion (mirrors get_all() fix #2516).
            artists = (
                session.query(Artist)
                .options(
                    selectinload(Artist.tracks).selectinload(Track.genres),
                    selectinload(Artist.albums)
                )
                .filter(Artist.name.ilike(search_term))
                .order_by(Artist.name)
                .limit(limit)
                .offset(offset)
                .all()
            )

            for artist in artists:
                session.expunge(artist)
            return artists, total
        finally:
            session.close()

    def get_all_artists(self) -> list[Artist]:
        """Get all artists without pagination (for batch operations)

        Returns:
            List of all artists in the database with tracks and albums eagerly loaded.

        Note:
            Uses selectinload to avoid DetachedInstanceError when accessing .tracks
            or .albums on returned objects after the session is closed (fixes #2524).
        """
        session = self.get_session()
        try:
            artists = (
                session.query(Artist)
                .options(
                    selectinload(Artist.tracks),
                    selectinload(Artist.albums),
                )
                .all()
            )
            for artist in artists:
                session.expunge(artist)
            return artists
        finally:
            session.close()

    def update_artwork(
        self,
        artist_id: int,
        artwork_url: str,
        artwork_source: str,
        artwork_fetched_at: object | None = None
    ) -> bool:
        """Update artist artwork information

        Args:
            artist_id: ID of the artist to update
            artwork_url: URL of the artwork image
            artwork_source: Source of the artwork (e.g., 'MusicBrainz', 'Discogs', 'Last.fm')
            artwork_fetched_at: Timestamp when artwork was fetched (defaults to current UTC time)

        Returns:
            True if update successful, False if artist not found or update failed
        """
        from datetime import datetime, timezone

        session = self.get_session()
        try:
            artist = session.query(Artist).filter(Artist.id == artist_id).first()
            if not artist:
                return False

            artist.artwork_url = artwork_url
            artist.artwork_source = artwork_source
            artist.artwork_fetched_at = artwork_fetched_at or datetime.now(timezone.utc)

            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
