"""
Unified Configuration
~~~~~~~~~~~~~~~~~~~~

Main configuration class for audio processing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import math
from typing import Any, Literal

from ...dsp.constants import DEFAULT_FFT_SIZE
from ...utils.logging import debug
from .genre_profiles import create_default_genre_profiles, get_genre_profile
from .preset_profiles import PresetProfile, get_preset_profile
from .settings import AdaptiveConfig, GenreProfile

# The three processing modes, as one runtime-checkable source of truth.
#
# `set_processing_mode`'s `Literal` annotation is static-only, so it validates
# nothing at runtime; this tuple is what the setter actually checks against, and
# it must stay in step with the `is_reference_mode` / `is_adaptive_mode` /
# `is_hybrid_mode` predicates below. Adding a fourth mode means adding it here,
# adding a predicate, and widening the `Literal` — all three, or a mode becomes
# settable that no dispatch branch recognises.
# The vocabulary lives in settings.py (#6218); re-exported here because
# set_processing_mode()'s error message and validators read it.
from .settings import PROCESSING_MODES, ProcessingMode  # noqa: F401 (re-export)


class UnifiedConfig:
    """
    Unified configuration system supporting both reference-based and adaptive processing
    """

    def __init__(
        self,
        # Core audio settings
        internal_sample_rate: int = 44100,
        max_length: float = 15 * 60,  # 15 minutes
        fft_size: int = DEFAULT_FFT_SIZE,

        # System settings
        temp_folder: str | None = None,

        # New adaptive settings
        adaptive: AdaptiveConfig | None = None,
        genre_profiles: dict[str, GenreProfile] | None = None,
    ):
        # Validate and set core audio settings
        # Real raises, not asserts: -O strips an assert (#6126).
        if not isinstance(internal_sample_rate, int) or isinstance(internal_sample_rate, bool) or internal_sample_rate <= 0:
            raise ValueError(f"internal_sample_rate must be a positive integer, got {internal_sample_rate!r}")
        if internal_sample_rate != 44100:
            debug(f"Using non-standard sample rate {internal_sample_rate}Hz")
        self.internal_sample_rate = internal_sample_rate

        if not max_length > 0:
            raise ValueError(f"max_length must be positive, got {max_length!r}")
        self.max_length = max_length

        # FFT size must be power of 2
        if not (fft_size > 1 and math.log2(fft_size).is_integer()):
            raise ValueError(f"fft_size must be a power of two greater than 1, got {fft_size!r}")
        self.fft_size = fft_size

        # System settings
        self.temp_folder = temp_folder

        # Adaptive processing configuration
        if adaptive is None:
            adaptive = AdaptiveConfig()
        self.adaptive = adaptive

        # Genre profiles
        if genre_profiles is None:
            genre_profiles = create_default_genre_profiles()
        self.genre_profiles = genre_profiles

        # Mastering profile/preset (only 'adaptive' is valid; see
        # preset_profiles.create_preset_profiles)
        self.mastering_profile = "adaptive"

        # Cross-dimensional guard (Phase 8 - mastering quality framework)
        # When True, each processing stage is measured and cross-dimensional
        # side effects are detected and compensated.
        self.enable_cross_dimensional_guard: bool = True

        # Quality gate: run QualityMetrics.compare_quality() on selected chunks
        # to verify output quality does not regress vs input. Diagnostics only:
        # the result is advisory and read by nothing in production, yet each
        # gated chunk costs ~2 s of CPU on the mastering path, so it is opt-in
        # (#5712).
        self.quality_gate_enabled: bool = False
        self.quality_gate_interval: int = 5  # Run every Nth chunk (0 = first only)

        debug(f"Unified config initialized: mode={self.adaptive.mode}, "
              f"SR={self.internal_sample_rate}Hz, FFT={self.fft_size}")

    def get_genre_profile(self, genre: str) -> GenreProfile:
        """Get processing profile for a specific genre"""
        return get_genre_profile(genre, self.genre_profiles)

    def set_processing_mode(self, mode: ProcessingMode) -> None:
        """
        Change the processing mode.

        Args:
            mode: One of "reference", "adaptive", "hybrid"

        Raises:
            ValueError: If the mode is not one of the three known modes.

        The `Literal` annotation is a static hint only — nothing enforced it at
        runtime, so an unknown string was accepted silently and left the config
        in a state where `is_adaptive_mode()`, `is_reference_mode()` AND
        `is_hybrid_mode()` all return False. Every mode-dispatch branch then
        falls through, which surfaces far from the assignment that caused it.

        Callers that already validate (`HybridProcessor.set_processing_mode`,
        the `Literal`-typed Pydantic model in `routers/processing_api.py`) were
        not the gap; `ProcessorFactory.get_or_create` builds the processor from
        the config it is handed without inspecting `mode`. Unknown names are
        rejected here rather than accepted silently.
        """
        if mode not in PROCESSING_MODES:
            raise ValueError(
                f"Invalid processing mode '{mode}'. "
                f"Valid modes: {', '.join(PROCESSING_MODES)}"
            )
        self.adaptive.mode = mode
        debug(f"Processing mode changed to: {mode}")

    def is_reference_mode(self) -> bool:
        """Check if using reference-based processing"""
        return self.adaptive.mode == "reference"

    def is_adaptive_mode(self) -> bool:
        """Check if using adaptive processing"""
        return self.adaptive.mode == "adaptive"

    def is_hybrid_mode(self) -> bool:
        """Check if using hybrid processing"""
        return self.adaptive.mode == "hybrid"

    def get_preset_profile(self) -> PresetProfile | None:
        """
        Get the current mastering preset profile.

        Returns:
            PresetProfile object for the current preset, or None if invalid preset name
        """
        return get_preset_profile(self.mastering_profile)

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary for serialization"""
        return {
            "internal_sample_rate": self.internal_sample_rate,
            "max_length": self.max_length,
            "fft_size": self.fft_size,
            "processing_mode": self.adaptive.mode,
            "adaptation_strength": self.adaptive.adaptation_strength,
            "enable_genre_detection": self.adaptive.enable_genre_detection,
            "chunk_size_ms": self.adaptive.chunk_size_ms,
            "latency_budget_ms": self.adaptive.latency_budget_ms
        }

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> UnifiedConfig:
        """Create configuration from dictionary (the caller's dict is not modified, #6126)"""
        config_dict = dict(config_dict)
        # Extract adaptive settings
        adaptive_settings = {}
        for key in ["processing_mode", "adaptation_strength", "enable_genre_detection",
                   "chunk_size_ms", "latency_budget_ms"]:
            if key in config_dict:
                adaptive_key = key.replace("processing_", "")
                adaptive_settings[adaptive_key] = config_dict.pop(key)

        # Create adaptive config
        adaptive = AdaptiveConfig(**adaptive_settings)

        # Create main config
        return cls(adaptive=adaptive, **config_dict)

    def __repr__(self) -> str:
        return (
            f"UnifiedConfig(mode={self.adaptive.mode}, "
            f"sample_rate={self.internal_sample_rate}Hz, "
            f"fft_size={self.fft_size}, "
            f"adaptation_strength={self.adaptive.adaptation_strength})"
        )
