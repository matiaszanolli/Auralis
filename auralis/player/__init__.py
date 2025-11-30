# -*- coding: utf-8 -*-

"""
Auralis Player Module
~~~~~~~~~~~~~~~~~~~~~

Real-time audio player with live mastering and adaptive DSP

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Based on Matchering Player components
"""

from .enhanced_audio_player import EnhancedAudioPlayer
from .config import PlayerConfig

__all__ = ["EnhancedAudioPlayer", "PlayerConfig"]