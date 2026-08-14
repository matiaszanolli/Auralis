"""
Dynamics Settings
~~~~~~~~~~~~~~~~~

Configuration classes for dynamics processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass
from enum import Enum

# Bound pairs shared by more than one field below. Promoted to named
# constants (#5022) after two pairs were independently re-typed as identical
# bare literals months apart with no cross-reference: CompressorSettings.ratio
# / DynamicsSettings.gate_ratio and CompressorSettings.threshold_db /
# DynamicsSettings.gate_threshold_db. (The third pair, CompressorSettings /
# LimiterSettings lookahead_ms, went with AdaptiveLimiter in #4873.) Fields
# whose valid range is not shared with another field keep their own inline
# bounds — LOOKAHEAD_MS_BOUNDS now has a single consumer but stays named
# because it is the compressor's documented contract, not a bare literal.
THRESHOLD_DB_BOUNDS: tuple[float, float] = (-80.0, 0.0)
RATIO_BOUNDS: tuple[float, float] = (1.0, 100.0)
LOOKAHEAD_MS_BOUNDS: tuple[float, float] = (0.0, 50.0)


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    """Clamp ``value`` to the closed interval ``(lo, hi)``."""
    lo, hi = bounds
    return max(lo, min(hi, value))


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
        self.threshold_db = _clamp(self.threshold_db, THRESHOLD_DB_BOUNDS)
        self.ratio = _clamp(self.ratio, RATIO_BOUNDS)
        self.attack_ms = _clamp(self.attack_ms, (0.01, 500.0))
        self.release_ms = _clamp(self.release_ms, (1.0, 5000.0))
        self.knee_db = _clamp(self.knee_db, (0.0, 24.0))
        self.lookahead_ms = _clamp(self.lookahead_ms, LOOKAHEAD_MS_BOUNDS)


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

    # Adaptive settings
    adaptation_speed: float = 0.1
    target_lufs: float = -14.0
    target_lra: float = 7.0  # Loudness Range

    def __post_init__(self) -> None:
        self.gate_threshold_db = _clamp(self.gate_threshold_db, THRESHOLD_DB_BOUNDS)
        self.gate_ratio = _clamp(self.gate_ratio, RATIO_BOUNDS)
        self.adaptation_speed = _clamp(self.adaptation_speed, (0.0, 1.0))
        self.target_lufs = _clamp(self.target_lufs, (-70.0, 0.0))
        self.target_lra = _clamp(self.target_lra, (0.0, 25.0))

        if self.compressor is None:
            self.compressor = CompressorSettings()
