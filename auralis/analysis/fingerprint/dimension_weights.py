"""
Dimension Weights
~~~~~~~~~~~~~~~~~

``DimensionWeights`` (the per-family distance weights and ``to_array()``
renormalization), split from distance.py (#6273).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class DimensionWeights:
    """Weights for fingerprint dimensions in similarity calculation"""

    # Frequency (7D) - Most important for perceived similarity
    sub_bass_pct: float = 0.04      # 4%
    bass_pct: float = 0.06           # 6%
    low_mid_pct: float = 0.05        # 5%
    mid_pct: float = 0.06            # 6%
    upper_mid_pct: float = 0.05      # 5%
    presence_pct: float = 0.04       # 4%
    air_pct: float = 0.03            # 3%
    # Subtotal: 33%

    # Dynamics (3D) - Very important
    lufs: float = 0.10               # 10%
    crest_db: float = 0.08           # 8%
    bass_mid_ratio: float = 0.05     # 5%
    # Subtotal: 23%

    # Temporal (4D) - Important for genre/style
    tempo_bpm: float = 0.08          # 8%
    rhythm_stability: float = 0.04   # 4%
    transient_density: float = 0.04  # 4%
    silence_ratio: float = 0.02      # 2%
    # Subtotal: 18%

    # Spectral (3D) - Moderate importance
    spectral_centroid: float = 0.05  # 5%
    spectral_rolloff: float = 0.04   # 4%
    spectral_flatness: float = 0.03  # 3%
    # Subtotal: 12%

    # Harmonic (3D) - Moderate importance
    harmonic_ratio: float = 0.04     # 4%
    pitch_stability: float = 0.03    # 3%
    chroma_energy: float = 0.02      # 2%
    # Subtotal: 9%

    # Variation (3D) - Low importance
    dynamic_range_variation: float = 0.02  # 2%
    loudness_variation_std: float = 0.02   # 2%
    peak_consistency: float = 0.01         # 1%
    # Subtotal: 5%

    # Stereo (2D) - Low importance
    stereo_width: float = 0.02       # 2%
    phase_correlation: float = 0.01  # 1%
    # Subtotal: 3%

    # TOTAL: 103% (normalized to 100% in to_array())

    def to_array(self) -> np.ndarray:
        """
        Convert weights to numpy array matching fingerprint dimension order

        Returns:
            25-element array of weights (normalized to sum=1.0)
        """
        weights = np.array([
            # Frequency (7D)
            self.sub_bass_pct,
            self.bass_pct,
            self.low_mid_pct,
            self.mid_pct,
            self.upper_mid_pct,
            self.presence_pct,
            self.air_pct,
            # Dynamics (3D)
            self.lufs,
            self.crest_db,
            self.bass_mid_ratio,
            # Temporal (4D)
            self.tempo_bpm,
            self.rhythm_stability,
            self.transient_density,
            self.silence_ratio,
            # Spectral (3D)
            self.spectral_centroid,
            self.spectral_rolloff,
            self.spectral_flatness,
            # Harmonic (3D)
            self.harmonic_ratio,
            self.pitch_stability,
            self.chroma_energy,
            # Variation (3D)
            self.dynamic_range_variation,
            self.loudness_variation_std,
            self.peak_consistency,
            # Stereo (2D)
            self.stereo_width,
            self.phase_correlation,
        ], dtype=np.float32)

        # Normalize to sum=1.0
        return np.asarray(weights / weights.sum(), dtype=np.float32)
