# -*- coding: utf-8 -*-

"""
Auralis Metadata Editor Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Audio file metadata editing and management

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .factory import create_metadata_editor
from .metadata_editor import MUTAGEN_AVAILABLE, MetadataEditor
from .models import MetadataUpdate

try:
    from mutagen import File as MutagenFile  # type: ignore[attr-defined]
except ImportError:
    MutagenFile = None

__all__ = [
    'MetadataUpdate',
    'MetadataEditor',
    'create_metadata_editor',
    'MUTAGEN_AVAILABLE',
    'MutagenFile',
]
