# -*- coding: utf-8 -*-

"""
Tag Mappings Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Format-specific metadata tag mappings

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Set

# Standard metadata fields (common across all formats)
STANDARD_FIELDS: Set[str] = {
    'title', 'artist', 'album', 'albumartist', 'year',
    'genre', 'track', 'disc', 'comment', 'bpm', 'composer',
    'publisher', 'lyrics', 'copyright'
}

# Format-specific tag mappings
TAG_MAPPINGS: Dict[str, Dict[str, str]] = {
    'mp3': {
        'title': 'TIT2',
        'artist': 'TPE1',
        'album': 'TALB',
        'albumartist': 'TPE2',
        'year': 'TDRC',
        'genre': 'TCON',
        'track': 'TRCK',
        'disc': 'TPOS',
        'comment': 'COMM::eng',
        'bpm': 'TBPM',
        'composer': 'TCOM',
        'publisher': 'TPUB',
        'lyrics': 'USLT::eng',
        'copyright': 'TCOP'
    },
    'flac': {
        # FLAC uses Vorbis comments (case-insensitive, but uppercase by convention)
        'title': 'TITLE',
        'artist': 'ARTIST',
        'album': 'ALBUM',
        'albumartist': 'ALBUMARTIST',
        'year': 'DATE',
        'genre': 'GENRE',
        'track': 'TRACKNUMBER',
        'disc': 'DISCNUMBER',
        'comment': 'COMMENT',
        'bpm': 'BPM',
        'composer': 'COMPOSER',
        'publisher': 'PUBLISHER',
        'lyrics': 'LYRICS',
        'copyright': 'COPYRIGHT'
    },
    'm4a': {
        # MP4/M4A uses freeform atoms
        'title': '\xa9nam',
        'artist': '\xa9ART',
        'album': '\xa9alb',
        'albumartist': 'aART',
        'year': '\xa9day',
        'genre': '\xa9gen',
        'track': 'trkn',
        'disc': 'disk',
        'comment': '\xa9cmt',
        'bpm': 'tmpo',
        'composer': '\xa9wrt',
        'publisher': '----:com.apple.iTunes:PUBLISHER',
        'lyrics': '\xa9lyr',
        'copyright': 'cprt'
    },
    'ogg': {
        # OGG Vorbis comments
        'title': 'TITLE',
        'artist': 'ARTIST',
        'album': 'ALBUM',
        'albumartist': 'ALBUMARTIST',
        'year': 'DATE',
        'genre': 'GENRE',
        'track': 'TRACKNUMBER',
        'disc': 'DISCNUMBER',
        'comment': 'COMMENT',
        'bpm': 'BPM',
        'composer': 'COMPOSER',
        'publisher': 'PUBLISHER',
        'lyrics': 'LYRICS',
        'copyright': 'COPYRIGHT'
    }
}

# Extension to format key mapping
EXTENSION_FORMAT_MAP: Dict[str, str] = {
    'mp3': 'mp3',
    'flac': 'flac',
    'm4a': 'm4a',
    'aac': 'm4a',
    'mp4': 'm4a',
    'ogg': 'ogg',
    'oga': 'ogg'
}


def get_format_key(extension: str) -> str:
    """
    Get format key for a file extension

    Args:
        extension: File extension (without dot)

    Returns:
        Format key for tag mappings
    """
    return EXTENSION_FORMAT_MAP.get(extension.lower(), 'flac')  # Default to FLAC tags
