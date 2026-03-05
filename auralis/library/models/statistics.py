"""
Statistics Models
~~~~~~~~~~~~~~~~~

Models for library-wide statistics and analytics

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class LibraryStats(Base, TimestampMixin):  # type: ignore[misc]
    """Model for library-wide statistics."""
    __tablename__ = 'library_stats'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    total_tracks: Mapped[int] = mapped_column(Integer, default=0)
    total_artists: Mapped[int] = mapped_column(Integer, default=0)
    total_albums: Mapped[int] = mapped_column(Integer, default=0)
    total_genres: Mapped[int] = mapped_column(Integer, default=0)
    total_playlists: Mapped[int] = mapped_column(Integer, default=0)
    total_duration: Mapped[float] = mapped_column(Float, default=0.0)  # Total duration in seconds
    total_filesize: Mapped[int] = mapped_column(Integer, default=0)  # Total filesize in bytes

    # Quality statistics
    avg_dr_rating: Mapped[Optional[float]] = mapped_column(Float)
    avg_lufs: Mapped[Optional[float]] = mapped_column(Float)
    avg_mastering_quality: Mapped[Optional[float]] = mapped_column(Float)

    # Last scan information
    last_scan_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_scan_duration: Mapped[Optional[float]] = mapped_column(Float)  # Scan duration in seconds
    files_scanned: Mapped[int] = mapped_column(Integer, default=0)
    new_files_found: Mapped[int] = mapped_column(Integer, default=0)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary"""
        return {
            'id': self.id,
            'total_tracks': self.total_tracks,
            'total_artists': self.total_artists,
            'total_albums': self.total_albums,
            'total_genres': self.total_genres,
            'total_playlists': self.total_playlists,
            'total_duration': self.total_duration,
            'total_duration_formatted': f"{self.total_duration // 3600:.0f}h {(self.total_duration % 3600) // 60:.0f}m",
            'total_filesize': self.total_filesize,
            'total_filesize_gb': self.total_filesize / (1024**3) if self.total_filesize else 0,
            'avg_dr_rating': self.avg_dr_rating,
            'avg_lufs': self.avg_lufs,
            'avg_mastering_quality': self.avg_mastering_quality,
            'last_scan_date': self.last_scan_date.isoformat() if self.last_scan_date else None,
            'last_scan_duration': self.last_scan_duration,
            'files_scanned': self.files_scanned,
            'new_files_found': self.new_files_found,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
