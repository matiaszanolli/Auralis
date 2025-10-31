# -*- coding: utf-8 -*-

"""
Scanner Configuration
~~~~~~~~~~~~~~~~~~~~

Configuration constants for library scanner

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

# Supported audio formats
AUDIO_EXTENSIONS = {
    '.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.wma',
    '.aiff', '.au', '.mp4', '.m4p', '.opus', '.webm'
}

# Common non-music directories to skip
SKIP_DIRECTORIES = {
    '.git', '.svn', 'node_modules', '__pycache__', '.vscode',
    'System Volume Information', '$RECYCLE.BIN', 'Thumbs.db',
    '.DS_Store', '.AppleDouble', '.LSOverride'
}

# Batch processing configuration
DEFAULT_BATCH_SIZE = 50

# File hash configuration
HASH_CHUNK_SIZE = 8192  # 8KB chunks for hash calculation
