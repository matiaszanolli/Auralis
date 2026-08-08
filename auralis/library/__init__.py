"""
Auralis Library Management
~~~~~~~~~~~~~~~~~~~~~~~~~

Music library database integration for Auralis

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .database import LibraryDatabase
from .models import Album, Artist, Genre, Playlist, Track
from .scanner import AudioFileInfo, LibraryScanner, ScanResult

__all__ = [
    # LibraryDatabase is the supported entry point. LibraryManager — the
    # deprecated legacy facade over it, unconstructed in production since
    # #4619 — and its dead cache.py were deleted outright (#4915) rather
    # than held to the promised v2.0.0 removal: zero production callers
    # remained, so there was nothing left for the deprecation window to
    # protect.
    "LibraryDatabase",
    "Track", "Album", "Artist", "Genre", "Playlist",
    "LibraryScanner", "ScanResult", "AudioFileInfo"
]