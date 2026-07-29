"""
Continuous Processing Space
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Maps audio fingerprints to continuous parameter space for adaptive processing.
Replaces discrete presets with intelligent parameter generation.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _smooth_unit(value: float, center: float, scale: float) -> float:
    """Map an unbounded measurement smoothly into the open interval ``(0, 1)``."""
    return 0.5 + 0.5 * math.tanh((float(value) - center) / (2.0 * scale))


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
    stereo_width_target: float            # Target stereo width (0.0 to 1.0)

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
        Convert legacy preset names to preference vectors.

        This provides backward compatibility with the old preset system
        while allowing gradual migration to the continuous space.

        Args:
            preset: Preset name (adaptive, gentle, warm, bright, punchy, live)

        Returns:
            PreferenceVector representing the preset's characteristics
        """
        presets = {
            'adaptive': cls(),  # Neutral - pure content-driven processing

            'gentle': cls(
                dynamic_bias=0.3,      # Preserve dynamics more
                loudness_bias=-0.2,    # Quieter output
            ),

            'warm': cls(
                spectral_bias=-0.3,    # Darker/warmer tonality
                bass_boost=0.5,        # More bass
                treble_boost=-0.2,     # Less treble (smoother highs)
            ),

            'bright': cls(
                spectral_bias=0.5,     # Brighter tonality
                treble_boost=0.7,      # More treble
                bass_boost=-0.3,       # Less bass
            ),

            'punchy': cls(
                bass_boost=0.6,        # More bass punch
                dynamic_bias=-0.2,     # Allow more compression
                loudness_bias=0.3,     # Louder output
            ),

            'live': cls(
                dynamic_bias=0.4,      # Preserve live dynamics
                stereo_bias=0.2,       # Wider stereo field
                bass_boost=-0.2,       # Reduce bass (less mud)
            ),
        }

        return presets.get(preset.lower(), cls())

    def __str__(self) -> str:
        return (f"PreferenceVector("
                f"spectral={self.spectral_bias:+.1f}, "
                f"dynamic={self.dynamic_bias:+.1f}, "
                f"loudness={self.loudness_bias:+.1f})")


class ProcessingSpaceMapper:
    """
    Maps 25D audio fingerprints to 3D processing space coordinates.

    The mapper transforms the high-dimensional fingerprint into a compact
    3-dimensional representation that captures the essential characteristics
    for processing decisions:
    - Relative spectral balance
    - Dynamic variation
    - Integrated energy

    All mappings are smooth and strictly monotonic. The calibration constants
    are robust centers and scales from a deterministic 512-track corpus sample
    (July 2026); they center the coordinate system without creating content
    classes, branch boundaries, or clipped acceptance ranges.
    """

    _SPECTRAL_LOG_RATIO_CENTER = -1.6901
    _SPECTRAL_LOG_RATIO_SCALE = 0.5045
    _CENTROID_CENTER = 0.0986
    _CENTROID_SCALE = 0.0240
    _CREST_CENTER_DB = 13.4207
    _CREST_SCALE_DB = 1.7884
    _LOUDNESS_VARIATION_LOG_CENTER = 0.9680
    _LOUDNESS_VARIATION_LOG_SCALE = 0.3855
    _LUFS_CENTER = -14.3887
    _LUFS_SCALE = 2.7732
    _ENERGY_EPSILON = 1e-8

    def map_fingerprint_to_space(self, fingerprint: dict[str, float]) -> ProcessingCoordinates:
        """
        Convert 25D fingerprint to 3D processing space position.

        Args:
            fingerprint: 25D audio fingerprint dictionary

        Returns:
            ProcessingCoordinates with position in 3D space
        """
        spectral_balance = self._calculate_spectral_balance(fingerprint)
        dynamic_range = self._calculate_dynamic_range(fingerprint)
        energy_level = self._calculate_energy_level(fingerprint)

        return ProcessingCoordinates(
            spectral_balance=spectral_balance,
            dynamic_range=dynamic_range,
            energy_level=energy_level,
            fingerprint=fingerprint
        )

    def _calculate_spectral_balance(self, fp: dict[str, float]) -> float:
        """
        Calculate a continuous spectral coordinate from band energy and centroid.

        Args:
            fp: Fingerprint dictionary

        Returns:
            Spectral balance score (0.0 to 1.0)
        """
        low_energy = (
            fp.get('sub_bass_pct', 0.0)
            + fp['bass_pct']
            + fp.get('low_mid_pct', 0.0)
        )
        high_energy = (
            fp.get('upper_mid_pct', 0.0)
            + fp['presence_pct']
            + fp['air_pct']
        )
        log_high_low = math.log(
            (high_energy + self._ENERGY_EPSILON)
            / (low_energy + self._ENERGY_EPSILON)
        )

        band_coordinate = _smooth_unit(
            log_high_low,
            self._SPECTRAL_LOG_RATIO_CENTER,
            self._SPECTRAL_LOG_RATIO_SCALE,
        )
        centroid_coordinate = _smooth_unit(
            fp['spectral_centroid'],
            self._CENTROID_CENTER,
            self._CENTROID_SCALE,
        )

        return float(0.7 * band_coordinate + 0.3 * centroid_coordinate)

    def _calculate_dynamic_range(self, fp: dict[str, float]) -> float:
        """
        Calculate a continuous dynamics coordinate.

        Args:
            fp: Fingerprint dictionary

        Returns:
            Dynamic range score (0.0 to 1.0)
        """
        crest_coordinate = _smooth_unit(
            fp['crest_db'],
            self._CREST_CENTER_DB,
            self._CREST_SCALE_DB,
        )
        loudness_variation = max(0.0, fp.get('loudness_variation_std', 0.0))
        variation_coordinate = _smooth_unit(
            math.log1p(loudness_variation),
            self._LOUDNESS_VARIATION_LOG_CENTER,
            self._LOUDNESS_VARIATION_LOG_SCALE,
        )

        # ``dynamic_range_variation`` is intentionally excluded here. The
        # July-2026 corpus pass found the existing metric saturated at 1.0 for
        # every one of 508 successful tracks, so it carries no mastering signal.
        return float(0.75 * crest_coordinate + 0.25 * variation_coordinate)

    def _calculate_energy_level(self, fp: dict[str, float]) -> float:
        """
        Calculate a continuous energy coordinate from integrated loudness.

        Args:
            fp: Fingerprint dictionary

        Returns:
            Energy level score (0.0 to 1.0)
        """
        return _smooth_unit(fp['lufs'], self._LUFS_CENTER, self._LUFS_SCALE)
