"""
Library Repository Layer
~~~~~~~~~~~~~~~~~~~~~~~

Data access layer for library database operations

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .album_repository import AlbumRepository
from .artist_repository import ArtistRepository
from .base import BaseRepository
from .factory import RepositoryFactory
from .fingerprint_repository import FingerprintRepository
from .fingerprint_scheduler_repository import FingerprintSchedulerRepository
from .fingerprint_stats_repository import FingerprintStatsRepository
from .genre_repository import GenreRepository
from .playlist_repository import PlaylistRepository
from .processing_job_repository import ProcessingJobRepository
from .queue_history_repository import QueueHistoryRepository
from .settings_repository import SettingsRepository
from .similarity_graph_repository import SimilarityGraphRepository
from .stats_repository import StatsRepository
from .track_repository import TrackRepository

__all__ = [
    'BaseRepository',
    'TrackRepository',
    'AlbumRepository',
    'ArtistRepository',
    'PlaylistRepository',
    'GenreRepository',
    'StatsRepository',
    'FingerprintRepository',
    'FingerprintSchedulerRepository',
    'FingerprintStatsRepository',
    'SettingsRepository',
    'QueueHistoryRepository',
    'ProcessingJobRepository',
    'SimilarityGraphRepository',
    'RepositoryFactory',
]
