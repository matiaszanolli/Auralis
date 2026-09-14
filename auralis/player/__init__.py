"""
Auralis Player Module
~~~~~~~~~~~~~~~~~~~~~

Real-time audio player with live mastering and adaptive DSP

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Based on Matchering Player components
"""

from .config import PlayerConfig
from .enhanced_audio_player import AudioPlayer

__all__ = ["AudioPlayer", "PlayerConfig"]
