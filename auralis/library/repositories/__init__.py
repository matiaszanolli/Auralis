# -*- coding: utf-8 -*-

"""
Library Repository Layer
~~~~~~~~~~~~~~~~~~~~~~~

Data access layer for library database operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .album_repository import AlbumRepository
from .artist_repository import ArtistRepository
from .factory import RepositoryFactory
from .fingerprint_repository import FingerprintRepository
from .genre_repository import GenreRepository
from .playlist_repository import PlaylistRepository
from .queue_history_repository import QueueHistoryRepository
from .queue_repository import QueueRepository
from .queue_template_repository import QueueTemplateRepository
from .settings_repository import SettingsRepository
from .stats_repository import StatsRepository
from .track_repository import TrackRepository

__all__ = [
    'TrackRepository',
    'AlbumRepository',
    'ArtistRepository',
    'PlaylistRepository',
    'GenreRepository',
    'StatsRepository',
    'FingerprintRepository',
    'SettingsRepository',
    'QueueRepository',
    'QueueHistoryRepository',
    'QueueTemplateRepository',
    'RepositoryFactory',
]
