"""
Statistics Repository
~~~~~~~~~~~~~~~~~~~~

Data access layer for library statistics

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Album, Artist, Genre, Playlist, Track


class StatsRepository:
    """Repository for library statistics operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get_session(self) -> Session:
        return self.session_factory()

    def get_library_stats(self) -> dict[str, Any]:
        """
        Get comprehensive library statistics

        Returns:
            Dictionary with library statistics
        """
        session = self.get_session()
        try:
            stats = {
                'total_tracks': session.execute(select(func.count(Track.id))).scalar_one_or_none() or 0,
                'total_albums': session.execute(select(func.count(Album.id))).scalar_one_or_none() or 0,
                'total_artists': session.execute(select(func.count(Artist.id))).scalar_one_or_none() or 0,
                'total_genres': session.execute(select(func.count(Genre.id))).scalar_one_or_none() or 0,
                'total_playlists': session.execute(select(func.count(Playlist.id))).scalar_one_or_none() or 0,
                'total_duration': session.execute(select(func.sum(Track.duration))).scalar_one_or_none() or 0,
                'total_filesize': session.execute(select(func.sum(Track.filesize))).scalar_one_or_none() or 0,
                'total_plays': session.execute(select(func.sum(Track.play_count))).scalar_one_or_none() or 0,
                'favorite_count': session.execute(select(func.count(Track.id)).where(Track.favorite == True)).scalar_one_or_none() or 0,
            }

            # Calculate average audio quality metrics
            avg_dr = session.execute(select(func.avg(Track.dr_rating)).where(Track.dr_rating.isnot(None))).scalar_one_or_none()
            avg_lufs = session.execute(select(func.avg(Track.lufs_level)).where(Track.lufs_level.isnot(None))).scalar_one_or_none()

            stats['average_dr'] = float(avg_dr) if avg_dr else None
            stats['average_lufs'] = float(avg_lufs) if avg_lufs else None

            # Derived fields expected by frontend
            stats['avg_dr_rating'] = stats['average_dr']
            stats['avg_lufs'] = stats['average_lufs']

            # Format total duration as human-readable string
            total_secs = int(stats['total_duration'])
            if total_secs >= 86400:
                days = total_secs // 86400
                hours = (total_secs % 86400) // 3600
                stats['total_duration_formatted'] = f"{days}d {hours}h" if hours else f"{days}d"
            elif total_secs >= 3600:
                hours = total_secs // 3600
                mins = (total_secs % 3600) // 60
                stats['total_duration_formatted'] = f"{hours} hours" if not mins else f"{hours}h {mins}m"
            elif total_secs >= 60:
                stats['total_duration_formatted'] = f"{total_secs // 60} minutes"
            else:
                stats['total_duration_formatted'] = f"{total_secs} seconds"

            # Convert filesize bytes to GB
            stats['total_filesize_gb'] = round(stats['total_filesize'] / (1024 ** 3), 2)

            return stats

        finally:
            session.close()
