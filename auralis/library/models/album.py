"""
Album Model
~~~~~~~~~~~

ORM model for albums (#4511 split of `models/core.py`).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .artist import Artist
    from .track import Track

from sqlalchemy import Float, ForeignKey, Index, Integer, String, collate, text
from sqlalchemy.orm import Mapped, mapped_column, query_expression, relationship

from ._helpers import _safe_collection, _safe_scalar
from .base import Base, TimestampMixin


class Album(Base, TimestampMixin):
    """Model for albums."""
    __tablename__ = 'albums'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    artist_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('artists.id'))
    year: Mapped[int | None] = mapped_column(Integer)

    # migration_v002_to_v003.sql, declared so fresh databases (create_all)
    # match upgraded ones (#5321). idx_albums_artist_id arrives later, via
    # migration_v024_to_v025.sql (#6103): albums.artist_id had no index, so
    # correlated artist album counts and Artist.albums selectin loads
    # scanned the whole table.
    #
    # The two unique indexes (migration_v029_to_v030.sql, #5595) are what let
    # concurrent scans insert the same new album with ON CONFLICT DO NOTHING
    # and still end up with one row. They are partial because SQLite treats
    # NULLs as distinct in a unique index: an artist-less album is unique by
    # title alone. Titles compare exactly, as the lookup in
    # ``_get_or_create_album`` does.
    __table_args__ = (
        Index('idx_albums_title', collate(title, 'NOCASE')),
        Index('idx_albums_year', year),
        Index('idx_albums_artist_id', artist_id),
        Index(
            'uq_albums_title_artist', title, artist_id, unique=True,
            sqlite_where=text('artist_id IS NOT NULL'),
        ),
        Index(
            'uq_albums_title_ownerless', title, unique=True,
            sqlite_where=text('artist_id IS NULL'),
        ),
    )

    total_tracks: Mapped[int | None] = mapped_column(Integer)
    total_discs: Mapped[int | None] = mapped_column(Integer)

    # Album artwork
    artwork_path: Mapped[str | None] = mapped_column(String)  # Path to extracted album artwork

    # Album-level analysis
    avg_dr_rating: Mapped[float | None] = mapped_column(Float)
    avg_lufs: Mapped[float | None] = mapped_column(Float)
    mastering_consistency: Mapped[float | None] = mapped_column(Float)  # How consistent the mastering is across tracks

    # Relationships
    artist: Mapped[Artist | None] = relationship("Artist", back_populates="albums")
    tracks: Mapped[list[Track]] = relationship("Track", back_populates="album")

    # Populated by AlbumRepository.get_all()/.search()/.get_recent() via
    # with_expression() so a list view can report these aggregates without
    # materialising every album's whole `tracks` collection (#4777, mirrors
    # Playlist.track_count_expr/#4554). Left as None on any query that does
    # not ask for them (e.g. get_by_id, which legitimately needs
    # the full tracks collection anyway), in which case to_dict() falls back
    # to walking `tracks`.
    track_count_expr: Mapped[int | None] = query_expression()
    total_duration_expr: Mapped[float | None] = query_expression()

    def to_dict(self) -> dict[str, Any]:
        """
        Convert album to dictionary.

        Returns artwork_path as API URL instead of filesystem path
        to prevent leaking internal paths and enable browser loading.
        """
        # Convert filesystem path to API URL if artwork exists
        artwork_url = None
        if self.artwork_path:
            artwork_url = f"/api/albums/{self.id}/artwork"

        # Guarded relationship read (#4641) — AlbumRepository eager-loads it
        # on the paths that need it, so this is the backstop, not the
        # mechanism.
        artist = _safe_scalar(self, 'artist')

        # Prefer the SQL-computed aggregates when the query supplied them
        # (#4777), so a paginated list view never has to load the tracks
        # collection just to count()/sum() it.
        if self.track_count_expr is not None:
            track_count = self.track_count_expr
            total_duration = self.total_duration_expr or 0
        else:
            tracks = _safe_collection(self, 'tracks')
            track_count = len(tracks)
            total_duration = sum(t.duration for t in tracks if t.duration)

        return {
            'id': self.id,
            'title': self.title,
            'artist_id': self.artist_id,
            'year': self.year,
            # The tag-declared count; `track_count` below is the real row count,
            # which is what `total_tracks` means on the sibling responses (#5905).
            'declared_track_count': self.total_tracks,
            'total_discs': self.total_discs,
            'artwork_url': artwork_url,  # API URL, not filesystem path
            'avg_dr_rating': self.avg_dr_rating,
            'avg_lufs': self.avg_lufs,
            'mastering_consistency': self.mastering_consistency,
            # null when absent, as on GET /api/albums/{id}/tracks; the frontend
            # supplies the 'Unknown Artist' label at its API boundary (#5905,
            # which replaces the server-side string #5457 introduced).
            'artist': artist.name if artist else None,
            'track_count': track_count,
            'total_duration': total_duration,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
