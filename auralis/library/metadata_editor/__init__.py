# -*- coding: utf-8 -*-

"""
Auralis Metadata Editor Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Audio file metadata editing and management

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .models import MetadataUpdate
from .metadata_editor import MetadataEditor, MUTAGEN_AVAILABLE
from .factory import create_metadata_editor

try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None

__all__ = [
    'MetadataUpdate',
    'MetadataEditor',
    'create_metadata_editor',
    'MUTAGEN_AVAILABLE',
    'MutagenFile',
]
