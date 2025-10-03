# -*- coding: utf-8 -*-

"""
Audio Loaders
~~~~~~~~~~~~~

Format-specific audio loading implementations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .soundfile_loader import load_with_soundfile
from .ffmpeg_loader import load_with_ffmpeg, check_ffmpeg

__all__ = [
    'load_with_soundfile',
    'load_with_ffmpeg',
    'check_ffmpeg',
]
