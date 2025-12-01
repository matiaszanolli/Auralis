# -*- coding: utf-8 -*-

"""
Auralis Library Database Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Database models for music library management

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

# Base and associations
from .base import Base, TimestampMixin, track_artist, track_genre, track_playlist

# Core models
from .core import Track, Album, Artist, Genre, Playlist, QueueState, QueueHistory, QueueTemplate

# Statistics
from .statistics import LibraryStats

# Settings
from .settings import UserSettings

# Fingerprint and similarity
from .fingerprint import TrackFingerprint, SimilarityGraph

# Schema versioning
from .schema import SchemaVersion

__all__ = [
    # Base
    'Base',
    'TimestampMixin',
    # Association tables
    'track_artist',
    'track_genre',
    'track_playlist',
    # Core models
    'Track',
    'Album',
    'Artist',
    'Genre',
    'Playlist',
    'QueueState',
    'QueueHistory',
    'QueueTemplate',
    # Statistics
    'LibraryStats',
    # Settings
    'UserSettings',
    # Fingerprint
    'TrackFingerprint',
    'SimilarityGraph',
    # Schema
    'SchemaVersion',
]
