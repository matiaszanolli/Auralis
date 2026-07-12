"""
Auralis - Real-time Audio Mastering Player
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unified Audio Processing and Real-time Mastering System

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Based on Matchering 2.0 by Sergree and contributors
"""

__title__ = "auralis"
# Mirror the single source of truth (auralis/version.py) so this never drifts (#4051).
from .version import __version__  # noqa: E402,F401
__author__ = "Auralis Team"
__license__ = "GPLv3"
__copyright__ = "Copyright (C) 2024 Auralis Team"

# Modern config and processing
from .core.config import (
    PresetProfile,
    UnifiedConfig,
    create_adaptive_config,
    create_reference_config,
    get_preset_profile,
)
from .core.hybrid_processor import HybridProcessor, process_adaptive, process_reference

# Results and output handling
from .io.results import Result, pcm16, pcm24

# Real-time player (Modern implementation with adaptive DSP)
from .player import AudioPlayer
from .player.config import PlayerConfig

# Logging
from .utils.logging import set_log_handler as log

# Main exports
__all__ = [
    "UnifiedConfig",     # Modern unified configuration
    "AudioPlayer",       # Real-time player with adaptive DSP
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
]