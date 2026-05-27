"""
Database Base and Associations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Base classes, association tables, and mixins for database models

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, PrimaryKeyConstraint, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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

# #3724 + #3725: composite PK on (track_id, playlist_id) gives us the
# DB-level uniqueness guarantee that PlaylistRepository.add_track now
# leans on (INSERT OR IGNORE in repository code). The explicit
# `position` column replaces the previous reliance on SQLAlchemy's
# implicit secondary-table ordering — two concurrent appends now
# resolve their position via SELECT MAX(position)+1 in a single
# transaction instead of racing on `len(playlist.tracks)`.
# Migration v015→v016 (migration_v015_to_v016.sql) rebuilds existing
# tables with the same shape and backfills position from the existing
# insertion order so visible UI order is preserved.
track_playlist = Table(
    'track_playlist', Base.metadata,
    Column('track_id', Integer, ForeignKey('tracks.id'), nullable=False),
    Column('playlist_id', Integer, ForeignKey('playlists.id'), nullable=False),
    Column('position', Integer, nullable=False, default=0),
    PrimaryKeyConstraint('track_id', 'playlist_id', name='pk_track_playlist'),
    Index('ix_track_playlist_playlist_position', 'playlist_id', 'position'),
)


class TimestampMixin:
    """Mixin to add creation and modification timestamps."""
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
