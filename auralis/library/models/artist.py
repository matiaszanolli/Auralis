"""
Artist Model
~~~~~~~~~~~~

ORM model for artists (#4511 split of `models/core.py`).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from .album import Album
    from .track import Track

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, query_expression, relationship

from ._helpers import _safe_collection
from .base import Base, TimestampMixin, track_artist


class Artist(Base, TimestampMixin):
    """Model for artists."""
    __tablename__ = 'artists'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    normalized_name: Mapped[str | None] = mapped_column(String, index=True)  # Canonical form for duplicate detection

    # Artist statistics
    total_plays: Mapped[int] = mapped_column(Integer, default=0)
    avg_mastering_quality: Mapped[float | None] = mapped_column(Float)

    # Artwork metadata (Phase 2: Real artist imagery)
    #
    # DELIBERATE EXCEPTION (#4526): `artwork_url` here holds an ABSOLUTE EXTERNAL
    # URL and is passed through to clients unmodified — unlike Album.to_dict()
    # and Track.to_dict(), which both rewrite their artwork to a same-origin
    # `/api/.../artwork` path. Artists have no local artwork file to serve: the
    # fetchers in auralis/services/artwork_service.py resolve a third-party CDN
    # URL and store only that, so there is nothing behind an /api path to serve.
    #
    # The consequence is that `artwork_url` carries two incompatible kinds of
    # value across the API depending on which entity it came from. Anything
    # consuming it must not assume a same-origin path — see `withArtworkSize()`
    # in the frontend, which now requires an `/api/` prefix for exactly this
    # reason. The browser is allowed to load these hosts by the `img-src`
    # allowlist in auralis-web/backend/config/middleware.py; adding a new
    # artwork source means adding its CDN host there too, or the image is
    # silently blocked and the UI falls back to a placeholder.
    artwork_url: Mapped[str | None] = mapped_column(Text)  # External URL to artist image
    artwork_source: Mapped[str | None] = mapped_column(String)  # 'musicbrainz', 'discogs', 'lastfm', etc.
    artwork_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)  # Last fetch timestamp

    # Relationships
    albums: Mapped[list[Album]] = relationship("Album", back_populates="artist")
    tracks: Mapped[list[Track]] = relationship("Track", secondary=track_artist, back_populates="artists")

    # Populated by ArtistRepository.get_all()/.search() via with_expression()
    # so a list view can report these counts without hydrating every Track row
    # belonging to every artist on the page (#5084, mirroring
    # Album.track_count_expr/#4777). Left as None on any query that does not
    # ask for them (get_by_id/get_by_name legitimately need the collections
    # anyway), in which case to_dict() falls back to walking them.
    track_count_expr: Mapped[int | None] = query_expression()
    album_count_expr: Mapped[int | None] = query_expression()

    # Distinct genre names across the artist's tracks, set by
    # ArtistRepository's list reads from one grouped query (#5084). Not a
    # mapped column and not a query_expression: SQLite's group_concat cannot
    # take both DISTINCT and a separator, and a comma-joined string would be
    # ambiguous for a genre name containing a comma. ClassVar so SQLAlchemy's
    # annotation scanning leaves it alone; None means "this query did not ask
    # for genres", which is different from "this artist has none".
    genre_names: ClassVar[list[str] | None] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert artist to dictionary"""
        # Prefer the SQL-computed counts when the query supplied them (#5084);
        # otherwise fall back to guarded relationship reads (#4641 — see
        # Album.to_dict).
        if self.track_count_expr is not None:
            track_count = self.track_count_expr
            album_count = self.album_count_expr or 0
        else:
            track_count = len(_safe_collection(self, 'tracks'))
            album_count = len(_safe_collection(self, 'albums'))

        return {
            'id': self.id,
            'name': self.name,
            'normalized_name': self.normalized_name,
            'total_plays': self.total_plays,
            'avg_mastering_quality': self.avg_mastering_quality,
            'album_count': album_count,
            'track_count': track_count,
            'artwork_url': self.artwork_url,  # Include artwork URL
            'artwork_source': self.artwork_source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Set by ArtistRepository's list reads (#5084) — see genre_names.
            'genres': self.genre_names,
        }
