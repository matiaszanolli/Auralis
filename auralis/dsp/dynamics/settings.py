"""
Dynamics Settings
~~~~~~~~~~~~~~~~~

Configuration classes for dynamics processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass
from enum import Enum


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

    def __post_init__(self) -> None:
        self.threshold_db = max(-80.0, min(0.0, self.threshold_db))
        self.ratio = max(1.0, min(100.0, self.ratio))
        self.attack_ms = max(0.01, min(500.0, self.attack_ms))
        self.release_ms = max(1.0, min(5000.0, self.release_ms))
        self.knee_db = max(0.0, min(24.0, self.knee_db))
        self.lookahead_ms = max(0.0, min(50.0, self.lookahead_ms))


@dataclass
class LimiterSettings:
    """Limiter configuration"""
    threshold_db: float = -1.0
    release_ms: float = 50.0
    lookahead_ms: float = 5.0
    isr_enabled: bool = True  # Inter-sample peak detection
    oversampling: int = 4

    def __post_init__(self) -> None:
        self.threshold_db = max(-40.0, min(0.0, self.threshold_db))
        self.release_ms = max(1.0, min(2000.0, self.release_ms))
        self.lookahead_ms = max(0.0, min(50.0, self.lookahead_ms))
        # Oversampling must be a power of 2 in [1, 8]
        valid_oversampling = {1, 2, 4, 8}
        if self.oversampling not in valid_oversampling:
            self.oversampling = min(valid_oversampling, key=lambda x: abs(x - self.oversampling))


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
    compressor: CompressorSettings | None = None

    enable_limiter: bool = True
    limiter: LimiterSettings | None = None

    # Adaptive settings
    adaptation_speed: float = 0.1
    target_lufs: float = -14.0
    target_lra: float = 7.0  # Loudness Range

    def __post_init__(self) -> None:
        if self.compressor is None:
            self.compressor = CompressorSettings()
        if self.limiter is None:
            self.limiter = LimiterSettings()
