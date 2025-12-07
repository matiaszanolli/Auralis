# -*- coding: utf-8 -*-

"""
Statistics Repository
~~~~~~~~~~~~~~~~~~~~

Data access layer for library statistics

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Any, Callable
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Track, Album, Artist, Genre, Playlist


class StatsRepository:
    """Repository for library statistics operations"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get_session(self) -> Session:
        return self.session_factory()

    def get_library_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive library statistics

        Returns:
            Dictionary with library statistics
        """
        session = self.get_session()
        try:
            stats = {
                'total_tracks': session.query(func.count(Track.id)).scalar() or 0,
                'total_albums': session.query(func.count(Album.id)).scalar() or 0,
                'total_artists': session.query(func.count(Artist.id)).scalar() or 0,
                'total_genres': session.query(func.count(Genre.id)).scalar() or 0,
                'total_playlists': session.query(func.count(Playlist.id)).scalar() or 0,
                'total_duration': session.query(func.sum(Track.duration)).scalar() or 0,
                'total_filesize': session.query(func.sum(Track.filesize)).scalar() or 0,
                'total_plays': session.query(func.sum(Track.play_count)).scalar() or 0,
                'favorite_count': session.query(func.count(Track.id)).filter(Track.favorite == True).scalar() or 0,
            }

            # Calculate average audio quality metrics
            avg_dr = session.query(func.avg(Track.dr_rating)).filter(Track.dr_rating.isnot(None)).scalar()
            avg_lufs = session.query(func.avg(Track.lufs_level)).filter(Track.lufs_level.isnot(None)).scalar()

            stats['average_dr'] = float(avg_dr) if avg_dr else None
            stats['average_lufs'] = float(avg_lufs) if avg_lufs else None

            return stats

        finally:
            session.close()
