# -*- coding: utf-8 -*-

"""
Library Repository Layer
~~~~~~~~~~~~~~~~~~~~~~~

Data access layer for library database operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .track_repository import TrackRepository
from .album_repository import AlbumRepository
from .artist_repository import ArtistRepository
from .playlist_repository import PlaylistRepository
from .genre_repository import GenreRepository
from .stats_repository import StatsRepository
from .fingerprint_repository import FingerprintRepository
from .settings_repository import SettingsRepository
from .queue_repository import QueueRepository
from .queue_history_repository import QueueHistoryRepository
from .queue_template_repository import QueueTemplateRepository

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
]
