"""
Playlist Model
~~~~~~~~~~~~~~

ORM model for playlists (#4511 split of `models/core.py`).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .track import Track

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, query_expression, relationship

from ._helpers import _safe_collection
from .base import Base, TimestampMixin, track_playlist


class Playlist(Base, TimestampMixin):
    """Model for playlists."""
    __tablename__ = 'playlists'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_smart: Mapped[bool] = mapped_column(Boolean, default=False)
    smart_criteria: Mapped[str | None] = mapped_column(Text)  # JSON string for smart playlist rules

    # Playlist-level mastering settings
    auto_master_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    mastering_profile: Mapped[str | None] = mapped_column(String, default='balanced')
    normalize_levels: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    # #3725: order_by the explicit `position` column on the association
    # table so the list returned to consumers is deterministic and
    # matches what add_track / reorder_track wrote, instead of
    # depending on SQLAlchemy's implicit row-insertion ordering.
    tracks: Mapped[list[Track]] = relationship(
        "Track",
        secondary=track_playlist,
        back_populates="playlists",
        order_by=track_playlist.c.position,
    )

    # Populated by PlaylistRepository.get_all() via with_expression() so a list
    # view can report these aggregates without materialising every playlist's
    # whole `tracks` collection (#4554). Left as None on any query that does not
    # ask for them, in which case to_dict() falls back to walking `tracks`.
    track_count_expr: Mapped[int | None] = query_expression()
    total_duration_expr: Mapped[float | None] = query_expression()

    def to_dict(self) -> dict[str, Any]:
        """Convert playlist to dictionary"""
        # Prefer SQL-computed aggregates when the query supplied them (#4554),
        # so a paginated list view never has to load the tracks collection.
        # Guarded relationship read (#4641) — see Album.to_dict — otherwise.
        if self.track_count_expr is not None:
            track_count = self.track_count_expr
            total_duration = self.total_duration_expr or 0
        else:
            tracks = _safe_collection(self, 'tracks')
            track_count = len(tracks)
            total_duration = sum(track.duration for track in tracks if track.duration)

        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_smart': self.is_smart,
            'smart_criteria': self.smart_criteria,
            'auto_master_enabled': self.auto_master_enabled,
            'mastering_profile': self.mastering_profile,
            'normalize_levels': self.normalize_levels,
            'track_count': track_count,
            'total_duration': total_duration,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Alias for frontend compatibility — frontend Playlist type uses modified_at (fixes #2269)
            'modified_at': self.updated_at.isoformat() if self.updated_at else None,
        }
