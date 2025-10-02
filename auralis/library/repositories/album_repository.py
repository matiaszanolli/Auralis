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
        """Get album by title"""
        session = self.get_session()
        try:
            return session.query(Album).filter(Album.title == title).first()
        finally:
            session.close()

    def get_all(self) -> List[Album]:
        """Get all albums"""
        session = self.get_session()
        try:
            return session.query(Album).order_by(Album.title).all()
        finally:
            session.close()
