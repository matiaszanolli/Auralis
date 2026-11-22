"""
Auralis Metadata Editor Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Audio file metadata editing and management

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .errors import UnreadableAudioFileError
from .factory import create_metadata_editor
from .metadata_editor import MetadataEditor
from .models import MetadataUpdate

from mutagen import File as MutagenFile

__all__ = [
    'MetadataUpdate',
    'MetadataEditor',
    'UnreadableAudioFileError',
    'create_metadata_editor',
    'MutagenFile',
]
