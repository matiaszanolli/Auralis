"""
Encoding module for audio output formats.

Provides WAV PCM encoding and other output format handlers.
"""

from .wav_encoder import WAVEncoder

__all__ = ['WAVEncoder']
