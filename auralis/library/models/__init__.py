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
from .core import (
    Album,
    Artist,
    Genre,
    Playlist,
    QueueHistory,
    QueueState,
    QueueTemplate,
    Track,
)

# Fingerprint and similarity
from .fingerprint import SimilarityGraph, TrackFingerprint

# Schema versioning
from .schema import SchemaVersion

# Settings
from .settings import UserSettings

# Statistics
from .statistics import LibraryStats

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
