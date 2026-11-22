"""
Continuous Space Types
~~~~~~~~~~~~~~~~~~~~~~

The coordinate/parameter dataclasses of the continuous processing space,
split from continuous_space.py (#6272); the mapper stays there.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from dataclasses import dataclass


@dataclass
class ProcessingCoordinates:
    """
    Position in 3D processing space.

    The processing space has two axes derived from the 25D fingerprint (a third, energy level, was
    removed in #6123: no parameter read it):
    - Spectral Balance: relative high-band to low-band energy
    - Dynamic Range: short-term peak/RMS and loudness variation
    """
    spectral_balance: float  # Increasing high-band energy relative to low-band energy
    dynamic_range: float     # Increasing crest and within-track loudness variation
    fingerprint: dict[str, float]  # Full 25D fingerprint for secondary parameters

    def __str__(self) -> str:
        return (f"ProcessingCoordinates("
                f"spectral={self.spectral_balance:.2f}, "
                f"dynamic={self.dynamic_range:.2f})")


@dataclass
class ProcessingParameters:
    """
    Complete set of DSP processing parameters.

    Generated from processing space coordinates. Every field is read by a ContinuousMode stage
    (pinned by tests/auralis/core/test_processing_parameters_have_readers_5576.py); fields that
    no stage read were deleted rather than kept for display (#6650).
    """
    # Loudness normalization
    target_lufs: float          # Target integrated loudness (LUFS)

    # EQ parameters
    eq_curve: dict[str, float]  # Frequency-specific gains and frequencies
    eq_blend: float             # EQ application strength (0.0 to 1.0)

    # Dynamics processing
    compression_params: dict[str, float]  # ``ratio`` and ``amount`` for the clip-blend compressor

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
                f"eq_blend={self.eq_blend:.2f}, "
                f"compression={self.compression_params.get('amount', 0.0):.2f})")
