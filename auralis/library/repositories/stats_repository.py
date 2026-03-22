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
            # Single atomic query for all track-level stats (counts, sums, averages)
            track_stats_row = session.execute(select(
                func.count(Track.id).label('total_tracks'),
                func.coalesce(func.sum(Track.duration), 0).label('total_duration'),
                func.coalesce(func.sum(Track.filesize), 0).label('total_filesize'),
                func.coalesce(func.sum(Track.play_count), 0).label('total_plays'),
                func.count(Track.id).filter(Track.favorite == True).label('favorite_count'),
                func.avg(Track.dr_rating).filter(Track.dr_rating.isnot(None)).label('avg_dr'),
                func.avg(Track.lufs_level).filter(Track.lufs_level.isnot(None)).label('avg_lufs'),
            )).one()

            # Single query for entity counts (albums, artists, genres, playlists)
            entity_counts = session.execute(select(
                select(func.count(Album.id)).correlate(None).scalar_subquery().label('total_albums'),
                select(func.count(Artist.id)).correlate(None).scalar_subquery().label('total_artists'),
                select(func.count(Genre.id)).correlate(None).scalar_subquery().label('total_genres'),
                select(func.count(Playlist.id)).correlate(None).scalar_subquery().label('total_playlists'),
            )).one()

            stats: dict[str, Any] = {
                'total_tracks': track_stats_row.total_tracks or 0,
                'total_albums': entity_counts.total_albums or 0,
                'total_artists': entity_counts.total_artists or 0,
                'total_genres': entity_counts.total_genres or 0,
                'total_playlists': entity_counts.total_playlists or 0,
                'total_duration': track_stats_row.total_duration or 0,
                'total_filesize': track_stats_row.total_filesize or 0,
                'total_plays': track_stats_row.total_plays or 0,
                'favorite_count': track_stats_row.favorite_count or 0,
            }

            avg_dr = track_stats_row.avg_dr
            avg_lufs = track_stats_row.avg_lufs
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
