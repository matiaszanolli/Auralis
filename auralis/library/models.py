"""
Auralis Library Database Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Database models for music library management
Integrated from existing library infrastructure

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

BACKWARD COMPATIBILITY WRAPPER
This file re-exports from the modular models package.
"""

# Re-export all models for backward compatibility
from .models import (  # Base; Association tables; Core models; Statistics; Settings; Fingerprint; Schema
    Album,
    Artist,
    Base,
    Genre,
    LibraryStats,
    Playlist,
    SchemaVersion,
    SimilarityGraph,
    TimestampMixin,
    Track,
    TrackFingerprint,
    UserSettings,
    track_artist,
    track_genre,
    track_playlist,
)

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
