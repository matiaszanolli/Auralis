# -*- coding: utf-8 -*-

"""
Album Repository
~~~~~~~~~~~~~~~

Data access layer for album operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from ..models import Album


class AlbumRepository:
    """Repository for album database operations"""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def get_session(self) -> Session:
        return self.session_factory()

    def get_by_title(self, title: str) -> Optional[Album]:
        """Get album by title with relationships loaded"""
        session = self.get_session()
        try:
            from sqlalchemy.orm import joinedload
            return (
                session.query(Album)
                .options(joinedload(Album.artist), joinedload(Album.tracks))
                .filter(Album.title == title)
                .first()
            )
        finally:
            session.close()

    def get_all(self) -> List[Album]:
        """Get all albums with relationships loaded"""
        session = self.get_session()
        try:
            from sqlalchemy.orm import joinedload
            return (
                session.query(Album)
                .options(joinedload(Album.artist), joinedload(Album.tracks))
                .order_by(Album.title)
                .all()
            )
        finally:
            session.close()
