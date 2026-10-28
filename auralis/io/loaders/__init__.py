"""
Audio Loaders
~~~~~~~~~~~~~

Format-specific audio loading implementations

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .ffmpeg_loader import load_with_ffmpeg
from .ffmpeg_path_guard import ffmpeg_input_path, reject_protocol_path
from .ffmpeg_probe import check_ffmpeg, check_ffprobe, ffprobe_command
from .ffmpeg_process import FFPROBE_TIMEOUT_S, SUBPROCESS_TEXT_KWARGS, redact_subprocess_output
from .soundfile_loader import load_with_soundfile

__all__ = [
    'FFPROBE_TIMEOUT_S',
    'SUBPROCESS_TEXT_KWARGS',
    'load_with_soundfile',
    'load_with_ffmpeg',
    'check_ffmpeg',
    'check_ffprobe',
    'ffprobe_command',
    'ffmpeg_input_path',
    'reject_protocol_path',
    'redact_subprocess_output',
]
