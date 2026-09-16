"""
Auralis Library Database Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Database models for music library management

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
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
    Track,
)

# Fingerprint and similarity
from .fingerprint import SimilarityGraph, TrackFingerprint

# Processing jobs (#5278)
from .processing_job import ProcessingJobRecord

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
    # Statistics
    'LibraryStats',
    # Settings
    'UserSettings',
    # Fingerprint
    'TrackFingerprint',
    'SimilarityGraph',
    # Processing jobs
    'ProcessingJobRecord',
    # Schema
    'SchemaVersion',
]
