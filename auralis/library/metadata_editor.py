"""
Auralis Metadata Editor
~~~~~~~~~~~~~~~~~~~~~~~

Audio file metadata editing and management
Supports MP3, FLAC, M4A, OGG, WAV and other formats via mutagen

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

BACKWARD COMPATIBILITY WRAPPER
This file re-exports from the modular metadata_editor package.
"""

# Re-export all public classes and functions for backward compatibility
from .metadata_editor import (
    MetadataEditor,
    MetadataUpdate,
    create_metadata_editor,
)

__all__ = [
    'MetadataUpdate',
    'MetadataEditor',
    'create_metadata_editor',
]
