"""
Audio Encoding Module
~~~~~~~~~~~~~~~~~~~~~

Provides audio encoding capabilities for streaming formats.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .wav_encoder import WAVEncoderError, encode_to_wav

__all__ = [
    'encode_to_wav',
    'WAVEncoderError',
]
