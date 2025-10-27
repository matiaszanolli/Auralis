"""
Audio Encoding Module
~~~~~~~~~~~~~~~~~~~~~

Provides audio encoding capabilities for streaming formats.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .webm_encoder import encode_to_webm_opus, WebMEncoderError

__all__ = ['encode_to_webm_opus', 'WebMEncoderError']
