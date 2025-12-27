# -*- coding: utf-8 -*-

"""
Auralis - Real-time Audio Mastering Player
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unified Audio Processing and Real-time Mastering System

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Based on Matchering 2.0 by Sergree and contributors
"""

__title__ = "auralis"
__version__ = "1.0.0"
__author__ = "Auralis Team"
__license__ = "GPLv3"
__copyright__ = "Copyright (C) 2024 Auralis Team"

from .analysis.content_analysis import analyze_audio_content

# Modern config and processing
from .core.config import (
    PresetProfile,
    UnifiedConfig,
    create_adaptive_config,
    create_reference_config,
    get_preset_profile,
)
from .core.hybrid_processor import HybridProcessor, process_adaptive, process_reference

# Core processing functions
from .core.processor import process

# Results and output handling
from .io.results import Result, pcm16, pcm24

# Real-time player (Modern implementation with adaptive DSP)
from .player import EnhancedAudioPlayer
from .player.config import PlayerConfig

# Logging
from .utils.logging import set_log_handler as log

# Main exports
__all__ = [
    "process",           # Core batch processing
    "UnifiedConfig",     # Modern unified configuration
    "EnhancedAudioPlayer",  # Real-time player with adaptive DSP (modern standard)
    "PlayerConfig",      # Player configuration
    "Result", "pcm16", "pcm24",  # Output formats
    "log",               # Logging
    # Modern system
    "create_adaptive_config",
    "create_reference_config",
    "PresetProfile",
    "get_preset_profile",
    "HybridProcessor",
    "process_adaptive",
    "process_reference",
    "analyze_audio_content"
]