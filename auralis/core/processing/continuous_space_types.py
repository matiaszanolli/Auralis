"""
Continuous Space Types
~~~~~~~~~~~~~~~~~~~~~~

The coordinate/parameter/preference dataclasses of the continuous processing space,
split from continuous_space.py (#6272); the mapper stays there.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from dataclasses import dataclass


@dataclass
class ProcessingCoordinates:
    """
    Position in 3D processing space.

    The processing space has three primary axes derived from the 25D fingerprint:
    - Spectral Balance: relative high-band to low-band energy
    - Dynamic Range: short-term peak/RMS and loudness variation
    - Energy Level: measured integrated loudness
    """
    spectral_balance: float  # Increasing high-band energy relative to low-band energy
    dynamic_range: float     # Increasing crest and within-track loudness variation
    energy_level: float      # Increasing integrated loudness
    fingerprint: dict[str, float]  # Full 25D fingerprint for secondary parameters

    def __str__(self) -> str:
        return (f"ProcessingCoordinates("
                f"spectral={self.spectral_balance:.2f}, "
                f"dynamic={self.dynamic_range:.2f}, "
                f"energy={self.energy_level:.2f})")


@dataclass
class ProcessingParameters:
    """
    Complete set of DSP processing parameters.

    Generated from processing space coordinates and user preferences.

    Not every field reaches a DSP stage: ``REPORTING_ONLY_FIELDS`` (in
    ``processing_parameter_readers``) names the display-only ones.
    """
    # Loudness normalization
    target_lufs: float          # Target integrated loudness (LUFS)
    peak_target_db: float       # Peak normalization target (dBFS)

    # EQ parameters
    eq_curve: dict[str, float]  # Frequency-specific gains and frequencies
    eq_blend: float             # EQ application strength (0.0 to 1.0)

    # Dynamics processing
    compression_params: dict[str, float]  # Compression settings
    expansion_params: dict[str, float]    # Expansion settings (de-mastering)
    dynamics_blend: float                 # Dynamics processing strength (0.0 to 1.0)

    # Limiting
    limiter_params: dict[str, float]      # Limiter settings

    # Stereo processing
    stereo_width_target: float            # Width FACTOR, 0.0-1.0 (0.5 = unity, 1.0 = max widening)

    # Track-level source loudness from a whole-track fingerprint (fixed-targets path): final
    # normalisation applies ONE gain (target_lufs - source_lufs) to every chunk instead of
    # re-levelling each to target_lufs, which flattened intra-track dynamics (#5552).
    # None means "unknown": measure per chunk.
    source_lufs: float | None = None

    def __str__(self) -> str:
        return (f"ProcessingParameters("
                f"LUFS={self.target_lufs:.1f}, "
                f"peak={self.peak_target_db:.2f}dB, "
                f"eq_blend={self.eq_blend:.2f}, "
                f"dynamics_blend={self.dynamics_blend:.2f})")


@dataclass
class PreferenceVector:
    """
    User preference as a bias in processing space.

    Instead of rigid presets, preferences act as gentle biases that
    shift the processing behavior in desired directions.
    """
    # Spectral preference: -1.0 (darker) to +1.0 (brighter)
    spectral_bias: float = 0.0

    # Dynamic preference: -1.0 (more compression) to +1.0 (more dynamics)
    dynamic_bias: float = 0.0

    # Loudness preference: -1.0 (quieter) to +1.0 (louder)
    loudness_bias: float = 0.0

    # Bass boost: 0.0 (none) to 1.0 (strong)
    bass_boost: float = 0.0

    # Treble boost: 0.0 (none) to 1.0 (strong)
    treble_boost: float = 0.0

    # Stereo width preference: -1.0 (narrower) to +1.0 (wider)
    stereo_bias: float = 0.0

    @classmethod
    def from_preset_name(cls, preset: str) -> PreferenceVector:
        """
        Convert a preset name to a preference vector.

        Auralis ships a single preset: 'adaptive' (content-driven, all biases neutral). The
        retired 'gentle'/'warm'/'bright'/'punchy'/'live' were removed rather than deprecated:
        none was reachable through a live API ('live' never was, #4861). Any other name,
        including those five, falls back to the neutral vector rather than raising.

        Args:
            preset: Preset name (only 'adaptive' is recognized)

        Returns:
            PreferenceVector representing the preset's characteristics
        """
        presets = {
            'adaptive': cls(),  # Neutral - pure content-driven processing
        }

        return presets.get(preset.lower(), cls())

    def __str__(self) -> str:
        return (f"PreferenceVector("
                f"spectral={self.spectral_bias:+.1f}, "
                f"dynamic={self.dynamic_bias:+.1f}, "
                f"loudness={self.loudness_bias:+.1f})")
