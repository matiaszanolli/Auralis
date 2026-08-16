"""
Encoding module for audio output formats.

Provides WAV PCM encoding and other output format handlers.
"""

from .wav_encoder import WAVEncoder, WAVEncoderError

__all__ = ['WAVEncoder', 'WAVEncoderError']
