"""
Auralis Library Management
~~~~~~~~~~~~~~~~~~~~~~~~~

Music library database integration for Auralis

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .manager import LibraryManager
from .models import Album, Artist, Genre, Playlist, Track
from .scanner import AudioFileInfo, LibraryScanner, ScanResult

__all__ = [
    "LibraryManager",
    "Track", "Album", "Artist", "Genre", "Playlist",
    "LibraryScanner", "ScanResult", "AudioFileInfo"
]