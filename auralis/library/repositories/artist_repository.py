# -*- coding: utf-8 -*-

"""
Artist Repository
~~~~~~~~~~~~~~~~

Data access layer for artist operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from ..models import Artist


class ArtistRepository:
    """Repository for artist database operations"""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def get_session(self) -> Session:
        return self.session_factory()

    def get_by_id(self, artist_id: int) -> Optional[Artist]:
        """Get artist by ID with relationships loaded"""
        session = self.get_session()
        try:
            from sqlalchemy.orm import joinedload
            return (
                session.query(Artist)
                .options(joinedload(Artist.tracks), joinedload(Artist.albums))
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
            return (
                session.query(Artist)
                .options(joinedload(Artist.tracks), joinedload(Artist.albums))
                .filter(Artist.name == name)
                .first()
            )
        finally:
            session.close()

    def get_all(self) -> List[Artist]:
        """Get all artists with relationships loaded"""
        session = self.get_session()
        try:
            from sqlalchemy.orm import joinedload
            return (
                session.query(Artist)
                .options(joinedload(Artist.tracks), joinedload(Artist.albums))
                .order_by(Artist.name)
                .all()
            )
        finally:
            session.close()
