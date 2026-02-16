"""
Database Base and Associations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Base classes, association tables, and mixins for database models

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Table
from sqlalchemy.orm import DeclarativeBase


# Create base for all models
class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Association tables for many-to-many relationships
track_artist = Table(
    'track_artist', Base.metadata,
    Column('track_id', Integer, ForeignKey('tracks.id')),
    Column('artist_id', Integer, ForeignKey('artists.id'))
)

track_genre = Table(
    'track_genre', Base.metadata,
    Column('track_id', Integer, ForeignKey('tracks.id')),
    Column('genre_id', Integer, ForeignKey('genres.id'))
)

track_playlist = Table(
    'track_playlist', Base.metadata,
    Column('track_id', Integer, ForeignKey('tracks.id')),
    Column('playlist_id', Integer, ForeignKey('playlists.id'))
)


class TimestampMixin:
    """Mixin to add creation and modification timestamps."""
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
