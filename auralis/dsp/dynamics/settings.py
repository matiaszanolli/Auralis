# -*- coding: utf-8 -*-

"""
Dynamics Settings
~~~~~~~~~~~~~~~~~

Configuration classes for dynamics processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DynamicsMode(Enum):
    """Dynamics processing modes"""
    TRANSPARENT = "transparent"      # Minimal processing, preserve dynamics
    MUSICAL = "musical"             # Musical compression, enhance groove
    BROADCAST = "broadcast"         # Consistent loudness for broadcast
    MASTERING = "mastering"         # Professional mastering chain
    ADAPTIVE = "adaptive"           # Content-aware automatic processing


@dataclass
class CompressorSettings:
    """Compressor configuration"""
    threshold_db: float = -18.0
    ratio: float = 4.0
    attack_ms: float = 10.0
    release_ms: float = 100.0
    knee_db: float = 2.0
    makeup_gain_db: float = 0.0
    enable_lookahead: bool = True
    lookahead_ms: float = 5.0


@dataclass
class LimiterSettings:
    """Limiter configuration"""
    threshold_db: float = -1.0
    release_ms: float = 50.0
    lookahead_ms: float = 5.0
    isr_enabled: bool = True  # Inter-sample peak detection
    oversampling: int = 4


@dataclass
class DynamicsSettings:
    """Complete dynamics processing settings"""
    mode: DynamicsMode = DynamicsMode.ADAPTIVE
    sample_rate: int = 44100

    # Processing chain configuration
    enable_gate: bool = True
    gate_threshold_db: float = -60.0
    gate_ratio: float = 10.0

    enable_compressor: bool = True
    compressor: Optional[CompressorSettings] = None

    enable_limiter: bool = True
    limiter: Optional[LimiterSettings] = None

    # Adaptive settings
    adaptation_speed: float = 0.1
    target_lufs: float = -14.0
    target_lra: float = 7.0  # Loudness Range

    def __post_init__(self) -> None:
        if self.compressor is None:
            self.compressor = CompressorSettings()
        if self.limiter is None:
            self.limiter = LimiterSettings()
