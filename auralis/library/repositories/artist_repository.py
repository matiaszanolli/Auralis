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

    def get_by_name(self, name: str) -> Optional[Artist]:
        """Get artist by name"""
        session = self.get_session()
        try:
            return session.query(Artist).filter(Artist.name == name).first()
        finally:
            session.close()

    def get_all(self) -> List[Artist]:
        """Get all artists"""
        session = self.get_session()
        try:
            return session.query(Artist).order_by(Artist.name).all()
        finally:
            session.close()
