"""
Genre Model
~~~~~~~~~~~

ORM model for music genres (#4511 split of `models/core.py`).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .track import Track

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, query_expression, relationship

from ._helpers import _safe_collection
from .base import Base, TimestampMixin, track_genre


class Genre(Base, TimestampMixin):
    """Model for music genres."""
    __tablename__ = 'genres'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    # Genre characteristics for auto-mastering
    preferred_profile: Mapped[str | None] = mapped_column(String, default='balanced')  # warm, bright, punchy, balanced
    typical_dr_range: Mapped[str | None] = mapped_column(String)  # "8-12" for example
    typical_lufs_range: Mapped[str | None] = mapped_column(String)  # "-14 to -10" for example

    # Relationships
    tracks: Mapped[list[Track]] = relationship("Track", secondary=track_genre, back_populates="genres")

    # Populated by GenreRepository.get_all()/.search() via with_expression(), so
    # a list page reports the count without hydrating every Track row a genre
    # owns (#5111, mirroring Artist/#5084 and Album/#4777). None on queries that
    # do not ask for it (get_by_id/get_by_name load the collection instead), in
    # which case to_dict() falls back to walking `tracks`.
    track_count_expr: Mapped[int | None] = query_expression()

    def to_dict(self) -> dict[str, Any]:
        """Convert genre to dictionary"""
        if self.track_count_expr is not None:
            track_count = self.track_count_expr
        else:
            # Guarded relationship read (#4641) — see Album.to_dict.
            track_count = len(_safe_collection(self, 'tracks'))
        return {
            'id': self.id,
            'name': self.name,
            'preferred_profile': self.preferred_profile,
            'typical_dr_range': self.typical_dr_range,
            'typical_lufs_range': self.typical_lufs_range,
            'track_count': track_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
