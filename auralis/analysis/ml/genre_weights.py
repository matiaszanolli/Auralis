# -*- coding: utf-8 -*-

"""
Genre Weights
~~~~~~~~~~~~~

Model weights and genre-specific adjustments for genre classification

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, List


def initialize_genre_weights(genres: List[str]) -> Dict[str, Dict[str, float]]:
    """
    Initialize model weights for genre classification

    This is a simplified linear model representation.
    In production, this would be replaced with actual trained model weights.

    Args:
        genres: List of genre names

    Returns:
        Dictionary mapping genres to feature weights
    """
    weights = {}
    for genre in genres:
        weights[genre] = {
            # Basic acoustic features
            'rms': np.random.normal(0, 0.1),
            'crest_factor_db': np.random.normal(0, 0.1),
            'zero_crossing_rate': np.random.normal(0, 0.1),

            # Spectral features
            'spectral_centroid': np.random.normal(0, 0.1),
            'spectral_rolloff': np.random.normal(0, 0.1),
            'spectral_bandwidth': np.random.normal(0, 0.1),
            'spectral_flatness': np.random.normal(0, 0.1),

            # Temporal features
            'tempo': np.random.normal(0, 0.1),
            'tempo_stability': np.random.normal(0, 0.1),
            'onset_rate': np.random.normal(0, 0.1),

            # Harmonic features
            'harmonic_ratio': np.random.normal(0, 0.1),

            # Energy distribution
            'energy_low': np.random.normal(0, 0.1),
            'energy_mid': np.random.normal(0, 0.1),
            'energy_high': np.random.normal(0, 0.1),

            # Bias term
            'bias': np.random.normal(0, 0.1)
        }

    # Apply genre-specific weight adjustments
    _apply_genre_specific_weights(weights)

    return weights


def _apply_genre_specific_weights(weights: Dict[str, Dict[str, float]]) -> None:
    """
    Apply genre-specific weight adjustments

    These adjustments encode musical knowledge about genre characteristics
    to make the classifier more realistic and accurate.

    Args:
        weights: Weight dictionary to modify in-place
    """

    # Electronic music characteristics
    if 'electronic' in weights:
        weights['electronic']['spectral_centroid'] = 0.3  # Brighter
        weights['electronic']['energy_high'] = 0.4        # More high-frequency energy
        weights['electronic']['tempo'] = 0.2              # Often faster

    # Classical music characteristics
    if 'classical' in weights:
        weights['classical']['crest_factor_db'] = 0.5     # Higher dynamic range
        weights['classical']['harmonic_ratio'] = 0.4      # More harmonic content
        weights['classical']['spectral_flatness'] = -0.3  # Less noise-like

    # Rock music characteristics
    if 'rock' in weights:
        weights['rock']['energy_mid'] = 0.4               # Strong midrange
        weights['rock']['onset_rate'] = 0.3               # More attacks
        weights['rock']['rms'] = 0.2                      # Generally louder

    # Jazz characteristics
    if 'jazz' in weights:
        weights['jazz']['harmonic_ratio'] = 0.3           # Complex harmonies
        weights['jazz']['tempo_stability'] = -0.2         # More tempo variation
        weights['jazz']['crest_factor_db'] = 0.3          # Dynamic playing

    # Hip-hop characteristics
    if 'hip_hop' in weights:
        weights['hip_hop']['energy_low'] = 0.5            # Strong bass
        weights['hip_hop']['onset_rate'] = 0.4            # Rhythmic attacks
        weights['hip_hop']['tempo'] = 0.1                 # Moderate tempo

    # Ambient characteristics
    if 'ambient' in weights:
        weights['ambient']['tempo'] = -0.4                # Slower
        weights['ambient']['onset_rate'] = -0.5           # Fewer attacks
        weights['ambient']['spectral_flatness'] = 0.2     # More atmospheric

    # Metal characteristics
    if 'metal' in weights:
        weights['metal']['energy_high'] = 0.3             # Bright, distorted guitars
        weights['metal']['rms'] = 0.4                     # Very loud
        weights['metal']['onset_rate'] = 0.5              # Fast attacks

    # Acoustic characteristics
    if 'acoustic' in weights:
        weights['acoustic']['harmonic_ratio'] = 0.4       # Natural harmonics
        weights['acoustic']['spectral_flatness'] = -0.2   # Pitched content
        weights['acoustic']['crest_factor_db'] = 0.3      # Dynamic range

    # Pop characteristics
    if 'pop' in weights:
        weights['pop']['energy_mid'] = 0.2                # Balanced midrange
        weights['pop']['tempo'] = 0.1                     # Moderate tempo
        weights['pop']['rms'] = 0.1                       # Moderate loudness

    # Country characteristics
    if 'country' in weights:
        weights['country']['harmonic_ratio'] = 0.3        # Harmonic instruments
        weights['country']['energy_mid'] = 0.3            # Vocal-focused midrange
        weights['country']['tempo_stability'] = 0.2       # Steady rhythm
