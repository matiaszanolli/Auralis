"""
Unified Configuration
~~~~~~~~~~~~~~~~~~~~

Main configuration class for audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import math
from typing import Any, Literal

from ...utils.logging import debug
from .genre_profiles import create_default_genre_profiles, get_genre_profile
from .preset_profiles import PresetProfile, get_available_presets, get_preset_profile
from .settings import AdaptiveConfig, GenreProfile, LimiterConfig


class UnifiedConfig:
    """
    Unified configuration system supporting both reference-based and adaptive processing
    """

    def __init__(
        self,
        # Core audio settings (from original Matchering)
        internal_sample_rate: int = 44100,
        processing_sample_rate: int | None = 48000,  # Downsample to this rate for faster processing (optional)
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
        temp_folder: str | None = None,
        limiter: LimiterConfig | None = None,

        # New adaptive settings
        adaptive: AdaptiveConfig | None = None,
        genre_profiles: dict[str, GenreProfile] | None = None,
    ):
        # Validate and set core audio settings
        assert internal_sample_rate > 0 and isinstance(internal_sample_rate, int)
        if internal_sample_rate != 44100:
            debug(f"Using non-standard sample rate {internal_sample_rate}Hz")
        self.internal_sample_rate = internal_sample_rate

        # Processing sample rate for I/O (downsampling for faster processing)
        # If set, audio files are downsampled to this rate during loading
        # Typical: 48000 Hz (saves 4x memory and time vs 192000 Hz)
        # Set to None to disable downsampling (use original file sample rate)
        if processing_sample_rate is not None:
            assert processing_sample_rate > 0 and isinstance(processing_sample_rate, int)
            if processing_sample_rate > internal_sample_rate:
                debug(f"Warning: processing_sample_rate ({processing_sample_rate}) > internal_sample_rate ({internal_sample_rate})")
        self.processing_sample_rate = processing_sample_rate

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
            genre_profiles = create_default_genre_profiles()
        self.genre_profiles = genre_profiles

        # Mastering profile/preset (adaptive, gentle, warm, bright, punchy)
        self.mastering_profile = "adaptive"

        # Continuous processing space (NEW - replaces discrete presets)
        # Set to True to use continuous parameter generation based on fingerprints
        # Set to False to use legacy preset-based processing
        self.use_continuous_space = True  # Default: enabled

        # Fingerprint analysis strategy (Phase 7)
        # "full-track": Analyze entire audio (100% accuracy, slower)
        # "sampling": Analyze 5s chunks at intervals (169x faster, 85.8% accuracy)
        self.fingerprint_strategy: str = "sampling"

        # Sampling interval in seconds (when strategy="sampling")
        # Recommended: 20.0 (25% coverage, 169x speedup)
        # Options: 10.0 (50% coverage, 75x speedup), 15.0 (33%, 116x), 20.0 (25%, 169x)
        self.fingerprint_sampling_interval: float = 20.0

        debug(f"Unified config initialized: mode={self.adaptive.mode}, "
              f"continuous_space={self.use_continuous_space}, "
              f"fingerprint_strategy={self.fingerprint_strategy}, "
              f"SR={self.internal_sample_rate}Hz, FFT={self.fft_size}")

    def get_genre_profile(self, genre: str) -> GenreProfile:
        """Get processing profile for a specific genre"""
        return get_genre_profile(genre, self.genre_profiles)

    def set_processing_mode(self, mode: Literal["reference", "adaptive", "hybrid"]) -> None:
        """Change the processing mode"""
        self.adaptive.mode = mode
        debug(f"Processing mode changed to: {mode}")

    def update_adaptive_settings(self, **kwargs: Any) -> None:
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

    def get_preset_profile(self) -> PresetProfile | None:
        """
        Get the current mastering preset profile.

        Returns:
            PresetProfile object for the current preset, or None if invalid preset name
        """
        return get_preset_profile(self.mastering_profile)

    def set_mastering_preset(self, preset_name: str) -> None:
        """
        Set the mastering preset.

        Args:
            preset_name: Name of the preset (adaptive, gentle, warm, bright, punchy)

        Raises:
            ValueError: If preset name is not valid
        """
        available = get_available_presets()
        if preset_name.lower() not in available:
            raise ValueError(
                f"Invalid preset '{preset_name}'. Available presets: {', '.join(available)}"
            )
        self.mastering_profile = preset_name.lower()
        debug(f"Mastering preset changed to: {preset_name}")

    def set_fingerprint_strategy(self, strategy: str, sampling_interval: float = 20.0) -> None:
        """
        Set fingerprint analysis strategy.

        Args:
            strategy: "full-track" or "sampling"
            sampling_interval: Interval in seconds between chunk starts (for sampling strategy)

        Raises:
            ValueError: If strategy is not valid
        """
        if strategy not in ("full-track", "sampling"):
            raise ValueError(f"Invalid fingerprint strategy '{strategy}'. Use 'full-track' or 'sampling'")

        if strategy == "sampling" and sampling_interval <= 0:
            raise ValueError(f"Sampling interval must be positive, got {sampling_interval}")

        self.fingerprint_strategy = strategy
        if strategy == "sampling":
            self.fingerprint_sampling_interval = sampling_interval

        debug(f"Fingerprint strategy changed to: {strategy}")
        if strategy == "sampling":
            debug(f"Sampling interval: {sampling_interval}s")

    def use_sampling_strategy(self) -> bool:
        """Check if using sampling-based fingerprinting."""
        return self.fingerprint_strategy == "sampling"

    def use_fulltrack_strategy(self) -> bool:
        """Check if using full-track fingerprinting."""
        return self.fingerprint_strategy == "full-track"

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, config_dict: dict[str, Any]) -> UnifiedConfig:
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

    def __repr__(self) -> str:
        return (
            f"UnifiedConfig(mode={self.adaptive.mode}, "
            f"sample_rate={self.internal_sample_rate}Hz, "
            f"fft_size={self.fft_size}, "
            f"adaptation_strength={self.adaptive.adaptation_strength})"
        )
