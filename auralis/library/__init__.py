"""
Auralis Library Management
~~~~~~~~~~~~~~~~~~~~~~~~~

Music library database integration for Auralis

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .database import LibraryDatabase
from .models import Album, Artist, Genre, Playlist, Track
from .scanner import AudioFileInfo, LibraryScanner, ScanResult

__all__ = [
    # LibraryDatabase is the entry point.
    "LibraryDatabase",
    "Track", "Album", "Artist", "Genre", "Playlist",
    "LibraryScanner", "ScanResult", "AudioFileInfo"
]