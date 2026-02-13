"""
Audio Feature Definitions
~~~~~~~~~~~~~~~~~~~~~~~~~

Data structures for audio features used in ML classification

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass


@dataclass
class AudioFeatures:
    """Comprehensive audio features for ML classification"""
    # Basic acoustic features
    rms: float
    peak: float
    crest_factor_db: float
    zero_crossing_rate: float

    # Spectral features
    spectral_centroid: float
    spectral_rolloff: float
    spectral_bandwidth: float
    spectral_contrast: list[float]
    spectral_flatness: float

    # Temporal features
    tempo: float
    tempo_stability: float
    onset_rate: float

    # Harmonic features
    harmonic_ratio: float
    fundamental_frequency: float

    # Energy distribution
    energy_low: float      # 0-250 Hz
    energy_mid: float      # 250-4000 Hz
    energy_high: float     # 4000+ Hz

    # Advanced features
    mfcc: list[float]      # Mel-frequency cepstral coefficients
    chroma: list[float]    # Chromagram features
    tonnetz: list[float]   # Tonal centroid features

    def to_vector(self) -> list[float]:
        """
        Convert features to flat vector for ML processing

        Returns:
            Flat list of all feature values
        """
        vector = [
            self.rms,
            self.peak,
            self.crest_factor_db,
            self.zero_crossing_rate,
            self.spectral_centroid,
            self.spectral_rolloff,
            self.spectral_bandwidth,
            self.spectral_flatness,
            self.tempo,
            self.tempo_stability,
            self.onset_rate,
            self.harmonic_ratio,
            self.fundamental_frequency,
            self.energy_low,
            self.energy_mid,
            self.energy_high,
        ]

        # Add list features
        vector.extend(self.spectral_contrast)
        vector.extend(self.mfcc)
        vector.extend(self.chroma)
        vector.extend(self.tonnetz)

        return vector

    def get_feature_names(self) -> list[str]:
        """Get names of all features in vector form"""
        names = [
            'rms', 'peak', 'crest_factor_db', 'zero_crossing_rate',
            'spectral_centroid', 'spectral_rolloff', 'spectral_bandwidth',
            'spectral_flatness', 'tempo', 'tempo_stability', 'onset_rate',
            'harmonic_ratio', 'fundamental_frequency',
            'energy_low', 'energy_mid', 'energy_high'
        ]

        # Add spectral contrast bands
        names.extend([f'spectral_contrast_{i}' for i in range(len(self.spectral_contrast))])

        # Add MFCC coefficients
        names.extend([f'mfcc_{i}' for i in range(len(self.mfcc))])

        # Add chroma bins
        names.extend([f'chroma_{i}' for i in range(len(self.chroma))])

        # Add tonnetz dimensions
        names.extend([f'tonnetz_{i}' for i in range(len(self.tonnetz))])

        return names
