"""
Audio Encoding Module
~~~~~~~~~~~~~~~~~~~~~

Provides audio encoding capabilities for streaming formats.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .wav_encoder import WAVEncoderError, encode_to_wav
from .webm_encoder import WebMEncoderError, encode_to_webm_opus

__all__ = [
    'encode_to_webm_opus',
    'WebMEncoderError',
    'encode_to_wav',
    'WAVEncoderError',
]
