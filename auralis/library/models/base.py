"""
Database Base and Associations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Base classes, association tables, and mixins for database models

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, PrimaryKeyConstraint, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Create base for all models
class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Association tables for many-to-many relationships
#
# SQLite FOREIGN KEY constraints index only the parent key, never the child
# column, so both association tables carry their own indexes on each side
# (#6103) — without them every Track.artists/Track.genres join, selectinload
# and .any() EXISTS is a full-table scan, and find_similar (run on every
# library track load while auto_reference_selection is on) took 20-40 s at
# 50k tracks. Fresh create_all databases get these declarations;
# migration v024→v025 adds them to databases upgraded from older versions.
track_artist = Table(
    'track_artist', Base.metadata,
    Column('track_id', Integer, ForeignKey('tracks.id')),
    Column('artist_id', Integer, ForeignKey('artists.id')),
    Index('ix_track_artist_track_id', 'track_id'),
    Index('ix_track_artist_artist_id', 'artist_id'),
)

track_genre = Table(
    'track_genre', Base.metadata,
    Column('track_id', Integer, ForeignKey('tracks.id')),
    Column('genre_id', Integer, ForeignKey('genres.id')),
    Index('ix_track_genre_track_id', 'track_id'),
    Index('ix_track_genre_genre_id', 'genre_id'),
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
