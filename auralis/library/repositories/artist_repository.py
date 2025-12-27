# -*- coding: utf-8 -*-

"""
Artist Repository
~~~~~~~~~~~~~~~~

Data access layer for artist operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Callable, List, Optional

from sqlalchemy.orm import Session

from ..models import Artist


class ArtistRepository:
    """Repository for artist database operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get_session(self) -> Session:
        return self.session_factory()

    def get_by_id(self, artist_id: int) -> Optional[Artist]:
        """Get artist by ID with relationships loaded"""
        session = self.get_session()
        try:
            from sqlalchemy.orm import joinedload

            from ..models import Album, Track
            return (
                session.query(Artist)
                .options(
                    joinedload(Artist.tracks).joinedload(Track.genres),
                    joinedload(Artist.albums).joinedload(Album.tracks)
                )
                .filter(Artist.id == artist_id)
                .first()
            )
        finally:
            session.close()

    def get_by_name(self, name: str) -> Optional[Artist]:
        """Get artist by name with relationships loaded"""
        session = self.get_session()
        try:
            from sqlalchemy.orm import joinedload

            from ..models import Track
            return (
                session.query(Artist)
                .options(
                    joinedload(Artist.tracks).joinedload(Track.genres),
                    joinedload(Artist.albums)
                )
                .filter(Artist.name == name)
                .first()
            )
        finally:
            session.close()

    def get_all(self, limit: int = 50, offset: int = 0, order_by: str = 'name') -> tuple[List[Artist], int]:
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
            from sqlalchemy.orm import joinedload

            from ..models import Track

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

            # Get paginated artists with all relationships eagerly loaded
            artists = (
                session.query(Artist)
                .options(
                    joinedload(Artist.tracks).joinedload(Track.genres),  # Load track genres
                    joinedload(Artist.albums)
                )
                .order_by(order_column)
                .limit(limit)
                .offset(offset)
                .all()
            )

            return artists, total
        finally:
            session.close()

    def search(self, query: str, limit: int = 50, offset: int = 0) -> tuple[List[Artist], int]:
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
            from sqlalchemy.orm import joinedload

            from ..models import Track

            # Get total count of matching artists
            total = (
                session.query(Artist)
                .filter(Artist.name.ilike(f'%{query}%'))
                .count()
            )

            # Get paginated results
            artists = (
                session.query(Artist)
                .options(
                    joinedload(Artist.tracks).joinedload(Track.genres),
                    joinedload(Artist.albums)
                )
                .filter(Artist.name.ilike(f'%{query}%'))
                .order_by(Artist.name)
                .limit(limit)
                .offset(offset)
                .all()
            )

            return artists, total
        finally:
            session.close()
