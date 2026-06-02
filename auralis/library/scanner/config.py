"""
Scanner Configuration
~~~~~~~~~~~~~~~~~~~~

Configuration constants for library scanner

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

# Supported audio formats — re-exported from the single source of truth
# (auralis.io.formats) so the scanner never ingests an extension the loader
# can't decode (#4109). Only formats with a working decode path are scanned;
# .mp4/.m4p/.webm (video/DRM containers) are intentionally excluded.
from auralis.io.formats import AUDIO_EXTENSIONS  # noqa: F401  (re-exported)

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
