"""
Genre Model
~~~~~~~~~~~

ORM model for music genres (#4511 split of `models/core.py`).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .track import Track

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    def to_dict(self) -> dict[str, Any]:
        """Convert genre to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'preferred_profile': self.preferred_profile,
            'typical_dr_range': self.typical_dr_range,
            'typical_lufs_range': self.typical_lufs_range,
            # Guarded relationship read (#4641) — see Album.to_dict.
            'track_count': len(_safe_collection(self, 'tracks')),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
