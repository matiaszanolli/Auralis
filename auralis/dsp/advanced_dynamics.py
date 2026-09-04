"""
Advanced Dynamics Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Dynamics component configuration and lifecycle management

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

The former chunk-processing path was retired in #5295. ContinuousMode owns
the production dynamics algorithm; this module retains the management facade
used by HybridProcessor and DynamicsManager.
"""

import threading
from typing import Any

from ..utils.logging import debug

# Import from refactored modules
from .dynamics import (
    AdaptiveCompressor,
    CompressorSettings,
    DynamicsMode,
    DynamicsSettings,
    EnvelopeFollower,
)

# Re-export for backward compatibility
__all__ = [
    "AdaptiveCompressor",
    "CompressorSettings",
    "DynamicsMode",
    "DynamicsProcessor",
    "DynamicsSettings",
    "EnvelopeFollower",
    "create_dynamics_processor",
]


class DynamicsProcessor:
    """Management facade for the configured dynamics components."""

    def __init__(self, settings: DynamicsSettings):
        """
        Initialize dynamics processor

        Args:
            settings: Dynamics processing configuration
        """
        # The management facade is shared by cached HybridProcessor instances;
        # serialize mode changes and lifecycle resets.
        self._lock = threading.RLock()

        self.settings = settings
        self.sample_rate = settings.sample_rate

        # Initialize processing components
        if settings.enable_compressor and settings.compressor is not None:
            self.compressor: AdaptiveCompressor | None = AdaptiveCompressor(
                settings.compressor, settings.sample_rate
            )
        else:
            self.compressor = None

        # Retained management state exposed by get_processing_info().
        self.gate_gain = 1.0

        threshold_db = (
            settings.compressor.threshold_db if settings.compressor else -18.0
        )
        ratio = settings.compressor.ratio if settings.compressor else 4.0
        self.adaptation_state = {
            "target_threshold": threshold_db,
            "target_ratio": ratio,
            "current_lufs": -14.0,
            "current_lra": 7.0,
        }

        # Preserve construction-time configuration so reset() remains a complete
        # lifecycle boundary even if a management caller edits exposed settings.
        self._initial_compressor_threshold_db = threshold_db
        self._initial_compressor_ratio = ratio
        self._initial_compressor_makeup_gain_db = (
            settings.compressor.makeup_gain_db if settings.compressor else 0.0
        )
        self._initial_adaptation_state = self.adaptation_state.copy()

        debug(f"Dynamics processor initialized in {settings.mode.value} mode")

    def get_processing_info(self) -> dict[str, Any]:
        """Get complete dynamics processing information"""
        info = {
            "mode": self.settings.mode.value,
            "adaptation_state": self.adaptation_state.copy(),
        }

        if self.compressor:
            info["compressor"] = self.compressor.get_current_state()

        info["gate"] = {
            "threshold_db": self.settings.gate_threshold_db,
            "current_gain": self.gate_gain,
        }

        return info

    def set_mode(self, mode: DynamicsMode) -> None:
        """Change the dynamics mode reported by the management API."""
        with self._lock:
            self.settings.mode = mode
            debug(f"Dynamics mode changed to: {mode.value}")

    def reset(self) -> None:
        """Reset component state and restore construction-time settings."""
        with self._lock:
            if self.compressor:
                self.compressor.reset()
                self.compressor.settings.threshold_db = (
                    self._initial_compressor_threshold_db
                )
                self.compressor.settings.ratio = self._initial_compressor_ratio
                self.compressor.settings.makeup_gain_db = (
                    self._initial_compressor_makeup_gain_db
                )

            self.gate_gain = 1.0
            self.adaptation_state = self._initial_adaptation_state.copy()

        debug("Dynamics processor reset")


def create_dynamics_processor(
    sample_rate: int,
    mode: DynamicsMode = DynamicsMode.ADAPTIVE,
    target_lufs: float = -14.0,
) -> DynamicsProcessor:
    """
    Factory function to create dynamics processor

    Args:
        sample_rate: Audio sample rate. Required (#4622) — a missing/wrong
            value silently mis-tunes the dynamics processing for the actual
            audio, with no error and no cue at the call site.
        mode: Processing mode
        target_lufs: Target loudness level

    Returns:
        Configured DynamicsProcessor
    """
    settings = DynamicsSettings(
        mode=mode, sample_rate=sample_rate, target_lufs=target_lufs
    )
    return DynamicsProcessor(settings)
