"""
Statistics Models
~~~~~~~~~~~~~~~~~

Models for library-wide statistics and analytics

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

from sqlalchemy import Column, DateTime, Float, Integer

from .base import Base, TimestampMixin


class LibraryStats(Base, TimestampMixin):  # type: ignore[misc]
    """Model for library-wide statistics."""
    __tablename__ = 'library_stats'

    id = Column(Integer, primary_key=True)
    total_tracks = Column(Integer, default=0)
    total_artists = Column(Integer, default=0)
    total_albums = Column(Integer, default=0)
    total_genres = Column(Integer, default=0)
    total_playlists = Column(Integer, default=0)
    total_duration = Column(Float, default=0.0)  # Total duration in seconds
    total_filesize = Column(Integer, default=0)  # Total filesize in bytes

    # Quality statistics
    avg_dr_rating = Column(Float)
    avg_lufs = Column(Float)
    avg_mastering_quality = Column(Float)

    # Last scan information
    last_scan_date = Column(DateTime)
    last_scan_duration = Column(Float)  # Scan duration in seconds
    files_scanned = Column(Integer, default=0)
    new_files_found = Column(Integer, default=0)

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
