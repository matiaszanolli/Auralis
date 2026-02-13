"""
Feature Extractors
~~~~~~~~~~~~~~~~~~

Audio feature extraction methods for content analysis

DEPRECATED: Use ContentAnalysisOperations instead. This module maintained for backward compatibility.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from .content_operations import ContentAnalysisOperations


class FeatureExtractor:
    """Extract audio features for content analysis

    Thin wrapper around ContentAnalysisOperations for backward compatibility.
    """

    def __init__(self, sample_rate: int = 44100):
        """
        Initialize feature extractor

        Args:
            sample_rate: Audio sample rate
        """
        self.sample_rate = sample_rate

    def calculate_dynamic_range(self, audio: np.ndarray) -> float:
        """Calculate dynamic range in dB"""
        return ContentAnalysisOperations.calculate_dynamic_range(audio, self.sample_rate)

    def calculate_spectral_spread(self, audio: np.ndarray) -> float:
        """Calculate spectral spread (bandwidth)"""
        return ContentAnalysisOperations.calculate_spectral_spread(audio, self.sample_rate)

    def calculate_spectral_flux(self, audio: np.ndarray) -> float:
        """Calculate spectral flux (rate of spectral change)"""
        return ContentAnalysisOperations.calculate_spectral_flux(audio)

    def estimate_attack_time(self, audio: np.ndarray) -> float:
        """Estimate average attack time in milliseconds"""
        return ContentAnalysisOperations.estimate_attack_time(audio, self.sample_rate)

    def estimate_fundamental_frequency(self, audio: np.ndarray) -> float:
        """Estimate fundamental frequency using autocorrelation"""
        return ContentAnalysisOperations.estimate_fundamental_frequency(audio, self.sample_rate)

    def calculate_harmonic_ratio(self, audio: np.ndarray) -> float:
        """Calculate harmonic to noise ratio"""
        return ContentAnalysisOperations.calculate_harmonic_ratio(audio)

    def calculate_inharmonicity(self, audio: np.ndarray) -> float:
        """Calculate inharmonicity (deviation from perfect harmonic series)"""
        return ContentAnalysisOperations.calculate_inharmonicity(audio, self.sample_rate)

    def calculate_rhythm_strength(self, audio: np.ndarray) -> float:
        """Calculate rhythmic strength"""
        return ContentAnalysisOperations.calculate_rhythm_strength(audio, self.sample_rate)

    def calculate_beat_consistency(self, audio: np.ndarray) -> float:
        """Calculate beat consistency (regularity)"""
        return ContentAnalysisOperations.calculate_beat_consistency(audio, self.sample_rate)

    def calculate_onset_strength(self, audio: np.ndarray) -> np.ndarray:
        """Calculate onset strength envelope"""
        return ContentAnalysisOperations.calculate_onset_strength(audio)

    def detect_onsets(self, audio: np.ndarray) -> np.ndarray:
        """Detect onset times in audio"""
        return ContentAnalysisOperations.detect_onsets(audio, self.sample_rate)


def create_feature_extractor(sample_rate: int = 44100) -> FeatureExtractor:
    """
    Factory function to create feature extractor

    Args:
        sample_rate: Audio sample rate

    Returns:
        Configured FeatureExtractor instance
    """
    return FeatureExtractor(sample_rate)
