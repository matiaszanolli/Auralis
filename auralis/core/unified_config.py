# -*- coding: utf-8 -*-

"""
Unified Configuration System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configuration for both reference-based and adaptive audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Unified configuration system for Matchering and Auralis integration
"""

import math
from typing import Optional, Dict, Any, Literal
from dataclasses import dataclass
from ..utils.logging import debug


@dataclass
class LimiterConfig:
    """Configuration for the audio limiter"""
    attack: float = 1.0
    hold: float = 1.0
    release: float = 3000.0
    attack_filter_coefficient: float = -2.0
    hold_filter_order: int = 1
    hold_filter_coefficient: float = 7.0
    release_filter_order: int = 1
    release_filter_coefficient: float = 800.0

    def __post_init__(self):
        assert self.attack > 0, "Attack time must be positive"
        assert self.hold > 0, "Hold time must be positive"
        assert self.release > 0, "Release time must be positive"
        assert self.hold_filter_order > 0, "Hold filter order must be positive"
        assert self.release_filter_order > 0, "Release filter order must be positive"


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive processing features"""
    # Processing mode
    mode: Literal["reference", "adaptive", "hybrid"] = "adaptive"

    # Content analysis settings
    enable_genre_detection: bool = True
    enable_tempo_analysis: bool = True
    enable_energy_analysis: bool = True

    # Adaptation settings
    adaptation_strength: float = 0.8  # 0.0 = no adaptation, 1.0 = full adaptation
    parameter_smoothing: float = 0.1  # Smoothing factor for parameter changes

    # Real-time processing
    chunk_size_ms: float = 20.0  # Processing chunk size in milliseconds
    latency_budget_ms: float = 20.0  # Maximum allowed latency

    # Quality control
    enable_quality_monitoring: bool = True
    auto_quality_adjustment: bool = True
    min_quality_level: Literal["basic", "medium", "high", "maximum"] = "medium"

    # User learning
    enable_user_learning: bool = True
    learning_rate: float = 0.05  # How quickly to adapt to user preferences

    # Psychoacoustic modeling
    enable_psychoacoustic_eq: bool = True
    critical_bands: int = 26  # Number of critical bands for analysis

    def __post_init__(self):
        assert 0.0 <= self.adaptation_strength <= 1.0, "Adaptation strength must be 0-1"
        assert 0.0 <= self.parameter_smoothing <= 1.0, "Parameter smoothing must be 0-1"
        assert 5.0 <= self.chunk_size_ms <= 100.0, "Chunk size must be 5-100ms"
        assert 10.0 <= self.latency_budget_ms <= 100.0, "Latency budget must be 10-100ms"
        assert 0.0 <= self.learning_rate <= 1.0, "Learning rate must be 0-1"
        assert 8 <= self.critical_bands <= 64, "Critical bands must be 8-64"


@dataclass
class GenreProfile:
    """Processing profile for a specific genre"""
    name: str
    target_lufs: float
    bass_boost_db: float
    midrange_clarity_db: float
    treble_enhancement_db: float
    compression_ratio: float
    stereo_width: float
    mastering_intensity: float

    def __post_init__(self):
        assert -30.0 <= self.target_lufs <= 0.0, "Target LUFS must be -30 to 0"
        assert -12.0 <= self.bass_boost_db <= 12.0, "Bass boost must be -12 to +12 dB"
        assert -12.0 <= self.midrange_clarity_db <= 12.0, "Midrange clarity must be -12 to +12 dB"
        assert -12.0 <= self.treble_enhancement_db <= 12.0, "Treble enhancement must be -12 to +12 dB"
        assert 1.0 <= self.compression_ratio <= 10.0, "Compression ratio must be 1-10"
        assert 0.0 <= self.stereo_width <= 2.0, "Stereo width must be 0-2"
        assert 0.0 <= self.mastering_intensity <= 1.0, "Mastering intensity must be 0-1"


class UnifiedConfig:
    """
    Unified configuration system supporting both reference-based and adaptive processing
    """

    def __init__(
        self,
        # Core audio settings (from original Matchering)
        internal_sample_rate: int = 44100,
        max_length: float = 15 * 60,  # 15 minutes
        max_piece_size: float = 15,  # 15 seconds
        threshold: float = 0.98,  # Peak threshold
        min_value: float = 1e-6,
        fft_size: int = 4096,

        # Advanced settings (from original Matchering)
        lin_log_oversampling: int = 4,
        rms_correction_steps: int = 4,
        clipping_samples_threshold: int = 8,
        limited_samples_threshold: int = 128,
        allow_equality: bool = False,
        lowess_frac: float = 0.0375,
        lowess_it: int = 0,
        lowess_delta: float = 0.001,

        # Preview settings
        preview_size: float = 30,
        preview_analysis_step: float = 5,
        preview_fade_size: float = 1,
        preview_fade_coefficient: float = 8,

        # System settings
        temp_folder: Optional[str] = None,
        limiter: Optional[LimiterConfig] = None,

        # New adaptive settings
        adaptive: Optional[AdaptiveConfig] = None,
        genre_profiles: Optional[Dict[str, GenreProfile]] = None,
    ):
        # Validate and set core audio settings
        assert internal_sample_rate > 0 and isinstance(internal_sample_rate, int)
        if internal_sample_rate != 44100:
            debug(f"Using non-standard sample rate {internal_sample_rate}Hz")
        self.internal_sample_rate = internal_sample_rate

        assert max_length > 0
        self.max_length = max_length

        assert max_piece_size > 0
        assert max_piece_size < max_length
        self.max_piece_size = max_piece_size * internal_sample_rate

        # Handle threshold (can be in dB or linear)
        if threshold < 0:
            threshold = 10 ** (threshold / 20)  # Convert dB to linear
        assert 0 < threshold <= 1
        self.threshold = float(threshold)

        assert 0 < min_value < 0.1
        self.min_value = min_value

        # FFT size must be power of 2
        assert fft_size > 1 and math.log2(fft_size).is_integer()
        self.fft_size = fft_size

        # Advanced processing settings
        assert lin_log_oversampling > 0 and isinstance(lin_log_oversampling, int)
        self.lin_log_oversampling = lin_log_oversampling

        assert rms_correction_steps >= 0 and isinstance(rms_correction_steps, int)
        self.rms_correction_steps = rms_correction_steps

        assert clipping_samples_threshold >= 0 and isinstance(clipping_samples_threshold, int)
        assert limited_samples_threshold > clipping_samples_threshold
        self.clipping_samples_threshold = clipping_samples_threshold
        self.limited_samples_threshold = limited_samples_threshold

        self.allow_equality = bool(allow_equality)

        # LOWESS filtering settings
        assert lowess_frac > 0
        assert lowess_it >= 0 and isinstance(lowess_it, int)
        assert lowess_delta >= 0
        self.lowess_frac = lowess_frac
        self.lowess_it = lowess_it
        self.lowess_delta = lowess_delta

        # Preview settings
        assert preview_size > 5
        assert preview_analysis_step > 1
        assert preview_fade_size > 0
        assert preview_fade_coefficient >= 2
        self.preview_size = preview_size * internal_sample_rate
        self.preview_analysis_step = preview_analysis_step * internal_sample_rate
        self.preview_fade_size = preview_fade_size * internal_sample_rate
        self.preview_fade_coefficient = preview_fade_coefficient

        # System settings
        self.temp_folder = temp_folder

        # Limiter configuration
        if limiter is None:
            limiter = LimiterConfig()
        self.limiter = limiter

        # Adaptive processing configuration
        if adaptive is None:
            adaptive = AdaptiveConfig()
        self.adaptive = adaptive

        # Genre profiles
        if genre_profiles is None:
            genre_profiles = self._create_default_genre_profiles()
        self.genre_profiles = genre_profiles

        debug(f"Unified config initialized: mode={self.adaptive.mode}, "
              f"SR={self.internal_sample_rate}Hz, FFT={self.fft_size}")

    def _create_default_genre_profiles(self) -> Dict[str, GenreProfile]:
        """Create default genre processing profiles"""
        return {
            "rock": GenreProfile(
                name="rock",
                target_lufs=-12.0,
                bass_boost_db=2.0,
                midrange_clarity_db=1.5,
                treble_enhancement_db=1.0,
                compression_ratio=3.0,
                stereo_width=0.8,
                mastering_intensity=0.8
            ),
            "pop": GenreProfile(
                name="pop",
                target_lufs=-14.0,
                bass_boost_db=1.5,
                midrange_clarity_db=2.0,
                treble_enhancement_db=1.5,
                compression_ratio=2.5,
                stereo_width=0.7,
                mastering_intensity=0.7
            ),
            "classical": GenreProfile(
                name="classical",
                target_lufs=-18.0,
                bass_boost_db=0.0,
                midrange_clarity_db=0.5,
                treble_enhancement_db=0.0,
                compression_ratio=1.5,
                stereo_width=0.9,
                mastering_intensity=0.3
            ),
            "electronic": GenreProfile(
                name="electronic",
                target_lufs=-10.0,
                bass_boost_db=4.0,
                midrange_clarity_db=2.0,
                treble_enhancement_db=2.0,
                compression_ratio=4.0,
                stereo_width=1.0,
                mastering_intensity=0.9
            ),
            "jazz": GenreProfile(
                name="jazz",
                target_lufs=-16.0,
                bass_boost_db=0.5,
                midrange_clarity_db=1.0,
                treble_enhancement_db=0.5,
                compression_ratio=2.0,
                stereo_width=0.8,
                mastering_intensity=0.4
            ),
            "hip_hop": GenreProfile(
                name="hip_hop",
                target_lufs=-11.0,
                bass_boost_db=3.0,
                midrange_clarity_db=2.5,
                treble_enhancement_db=1.0,
                compression_ratio=3.5,
                stereo_width=0.6,
                mastering_intensity=0.8
            ),
            "acoustic": GenreProfile(
                name="acoustic",
                target_lufs=-16.0,
                bass_boost_db=0.0,
                midrange_clarity_db=1.5,
                treble_enhancement_db=1.0,
                compression_ratio=1.8,
                stereo_width=0.7,
                mastering_intensity=0.4
            ),
            "ambient": GenreProfile(
                name="ambient",
                target_lufs=-20.0,
                bass_boost_db=1.0,
                midrange_clarity_db=0.0,
                treble_enhancement_db=2.0,
                compression_ratio=1.2,
                stereo_width=1.2,
                mastering_intensity=0.2
            )
        }

    def get_genre_profile(self, genre: str) -> GenreProfile:
        """Get processing profile for a specific genre"""
        genre_lower = genre.lower()
        if genre_lower in self.genre_profiles:
            return self.genre_profiles[genre_lower]
        else:
            # Return a balanced default profile
            debug(f"Unknown genre '{genre}', using default profile")
            return GenreProfile(
                name="default",
                target_lufs=-14.0,
                bass_boost_db=1.0,
                midrange_clarity_db=1.0,
                treble_enhancement_db=1.0,
                compression_ratio=2.5,
                stereo_width=0.8,
                mastering_intensity=0.6
            )

    def set_processing_mode(self, mode: Literal["reference", "adaptive", "hybrid"]):
        """Change the processing mode"""
        self.adaptive.mode = mode
        debug(f"Processing mode changed to: {mode}")

    def update_adaptive_settings(self, **kwargs):
        """Update adaptive processing settings"""
        for key, value in kwargs.items():
            if hasattr(self.adaptive, key):
                setattr(self.adaptive, key, value)
                debug(f"Updated adaptive setting: {key} = {value}")
            else:
                debug(f"Warning: Unknown adaptive setting '{key}'")

    def get_chunk_size_samples(self) -> int:
        """Get processing chunk size in samples"""
        return int(self.adaptive.chunk_size_ms * self.internal_sample_rate / 1000)

    def get_latency_budget_samples(self) -> int:
        """Get latency budget in samples"""
        return int(self.adaptive.latency_budget_ms * self.internal_sample_rate / 1000)

    def is_reference_mode(self) -> bool:
        """Check if using reference-based processing"""
        return self.adaptive.mode == "reference"

    def is_adaptive_mode(self) -> bool:
        """Check if using adaptive processing"""
        return self.adaptive.mode == "adaptive"

    def is_hybrid_mode(self) -> bool:
        """Check if using hybrid processing"""
        return self.adaptive.mode == "hybrid"

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization"""
        return {
            "internal_sample_rate": self.internal_sample_rate,
            "max_length": self.max_length,
            "max_piece_size": self.max_piece_size / self.internal_sample_rate,
            "threshold": self.threshold,
            "min_value": self.min_value,
            "fft_size": self.fft_size,
            "processing_mode": self.adaptive.mode,
            "adaptation_strength": self.adaptive.adaptation_strength,
            "enable_genre_detection": self.adaptive.enable_genre_detection,
            "enable_user_learning": self.adaptive.enable_user_learning,
            "chunk_size_ms": self.adaptive.chunk_size_ms,
            "latency_budget_ms": self.adaptive.latency_budget_ms
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "UnifiedConfig":
        """Create configuration from dictionary"""
        # Extract adaptive settings
        adaptive_settings = {}
        for key in ["processing_mode", "adaptation_strength", "enable_genre_detection",
                   "enable_user_learning", "chunk_size_ms", "latency_budget_ms"]:
            if key in config_dict:
                adaptive_key = key.replace("processing_", "")
                adaptive_settings[adaptive_key] = config_dict.pop(key)

        # Create adaptive config
        adaptive = AdaptiveConfig(**adaptive_settings)

        # Create main config
        return cls(adaptive=adaptive, **config_dict)

    def __repr__(self):
        return (
            f"UnifiedConfig(mode={self.adaptive.mode}, "
            f"sample_rate={self.internal_sample_rate}Hz, "
            f"fft_size={self.fft_size}, "
            f"adaptation_strength={self.adaptive.adaptation_strength})"
        )


# Convenience function for creating configurations
def create_adaptive_config(**kwargs) -> UnifiedConfig:
    """Create configuration optimized for adaptive processing"""
    adaptive_settings = {
        "mode": "adaptive",
        "enable_genre_detection": True,
        "enable_user_learning": True,
        "adaptation_strength": 0.8,
        **kwargs
    }
    return UnifiedConfig(adaptive=AdaptiveConfig(**adaptive_settings))


def create_reference_config(**kwargs) -> UnifiedConfig:
    """Create configuration for traditional reference-based processing"""
    adaptive_settings = {
        "mode": "reference",
        "enable_genre_detection": False,
        "enable_user_learning": False,
        "adaptation_strength": 0.0,
        **kwargs
    }
    return UnifiedConfig(adaptive=AdaptiveConfig(**adaptive_settings))


def create_hybrid_config(**kwargs) -> UnifiedConfig:
    """Create configuration for hybrid processing mode"""
    adaptive_settings = {
        "mode": "hybrid",
        "enable_genre_detection": True,
        "enable_user_learning": True,
        "adaptation_strength": 0.5,
        **kwargs
    }
    return UnifiedConfig(adaptive=AdaptiveConfig(**adaptive_settings))