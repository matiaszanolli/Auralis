# -*- coding: utf-8 -*-

"""
EQ Curve Presets
~~~~~~~~~~~~~~~

Genre-specific and content-aware EQ curve generation

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Optional, Any, List


# Genre-specific EQ curves (25 bands)
GENRE_CURVES = {
    'rock': np.array([2, 1, 0, 0, 1, 2, 1, 0, -1, 0, 1, 2, 1, 0, 0, 1, 2, 1, 0, -1, 0, 0, 0, 0, 0]),
    'pop': np.array([1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
    'classical': np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0]),
    'electronic': np.array([3, 2, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 2, 2, 2, 1, 1, 1, 0, 0, 0, 0]),
    'jazz': np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0]),
    'ambient': np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 2, 2, 1, 1, 0, 0, 0, 0]),
    'metal': np.array([2, 2, 1, 0, 0, 1, 2, 1, -1, -1, 0, 1, 2, 2, 1, 1, 2, 2, 1, 0, 0, 0, 0, 0, 0]),
    'hip-hop': np.array([3, 2, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 1, 2, 1, 1, 0, 0, 0, 0, 0, 0]),
    'country': np.array([1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]),
}


def generate_genre_eq_curve(genre: str, num_bands: int = 25) -> np.ndarray:
    """
    Generate EQ curve for specific genre

    Args:
        genre: Genre name (rock, pop, classical, electronic, jazz, ambient, etc.)
        num_bands: Number of frequency bands

    Returns:
        EQ curve as array of gain values in dB
    """
    genre_lower = genre.lower()

    if genre_lower in GENRE_CURVES:
        curve = GENRE_CURVES[genre_lower]
        if len(curve) >= num_bands:
            return curve[:num_bands]
        else:
            # Pad with zeros if needed
            padded = np.zeros(num_bands)
            padded[:len(curve)] = curve
            return padded
    else:
        return np.zeros(num_bands)  # Flat response for unknown genres


def apply_content_adaptation(gains: np.ndarray,
                            content_profile: Dict[str, Any],
                            critical_bands: List[Any]) -> np.ndarray:
    """
    Apply content-aware adaptations to EQ gains

    Adjusts EQ based on audio content characteristics like genre,
    energy level, and spectral balance.

    Args:
        gains: Initial EQ gains in dB
        content_profile: Dictionary with content analysis results
        critical_bands: List of CriticalBand objects

    Returns:
        Adapted EQ gains
    """
    adapted_gains = gains.copy()

    # Extract content characteristics
    genre = content_profile.get('genre', 'unknown')
    energy_level = content_profile.get('energy_level', 'medium')
    spectral_centroid = content_profile.get('spectral_centroid', 2000)

    # Apply genre-specific adaptations
    adapted_gains = _apply_genre_adaptation(adapted_gains, genre, critical_bands)

    # Apply energy level adaptations
    adapted_gains = _apply_energy_adaptation(adapted_gains, energy_level)

    # Apply spectral balance adaptations
    adapted_gains = _apply_spectral_adaptation(adapted_gains, spectral_centroid, critical_bands)

    return adapted_gains


def _apply_genre_adaptation(gains: np.ndarray,
                           genre: str,
                           critical_bands: List[Any]) -> np.ndarray:
    """Apply genre-specific EQ adaptations"""
    adapted_gains = gains.copy()

    if genre == 'classical':
        # Preserve natural tone - reduce EQ intensity
        adapted_gains *= 0.7
        # Slight treble enhancement for clarity
        for i, band in enumerate(critical_bands):
            if 4000 <= band.center_freq <= 8000:
                adapted_gains[i] += 0.5

    elif genre == 'rock':
        # Enhance punch and clarity
        for i, band in enumerate(critical_bands):
            if 100 <= band.center_freq <= 200:  # Bass punch
                adapted_gains[i] += 1.0
            elif 2000 <= band.center_freq <= 4000:  # Midrange clarity
                adapted_gains[i] += 0.8

    elif genre == 'electronic':
        # Enhance bass and treble
        for i, band in enumerate(critical_bands):
            if 50 <= band.center_freq <= 120:  # Sub-bass
                adapted_gains[i] += 1.5
            elif 8000 <= band.center_freq <= 16000:  # Treble sparkle
                adapted_gains[i] += 1.0

    elif genre == 'metal':
        # Aggressive bass and treble, scooped mids
        for i, band in enumerate(critical_bands):
            if 60 <= band.center_freq <= 150:  # Heavy bass
                adapted_gains[i] += 1.5
            elif 400 <= band.center_freq <= 1000:  # Scoop mids
                adapted_gains[i] -= 0.5
            elif 4000 <= band.center_freq <= 8000:  # Aggressive highs
                adapted_gains[i] += 1.2

    elif genre == 'jazz':
        # Natural midrange, gentle treble
        for i, band in enumerate(critical_bands):
            if 500 <= band.center_freq <= 3000:  # Natural mids
                adapted_gains[i] *= 0.8
            elif 6000 <= band.center_freq <= 12000:  # Gentle air
                adapted_gains[i] += 0.5

    return adapted_gains


def _apply_energy_adaptation(gains: np.ndarray, energy_level: str) -> np.ndarray:
    """Apply energy level-based adaptations"""
    adapted_gains = gains.copy()

    if energy_level == 'low':
        # Boost overall presence
        adapted_gains += 0.5
    elif energy_level == 'high':
        # Be more conservative to avoid harshness
        adapted_gains *= 0.8

    return adapted_gains


def _apply_spectral_adaptation(gains: np.ndarray,
                              spectral_centroid: float,
                              critical_bands: List[Any]) -> np.ndarray:
    """Apply spectral balance-based adaptations"""
    adapted_gains = gains.copy()

    if spectral_centroid < 1500:  # Dark content
        # Boost treble for clarity
        for i, band in enumerate(critical_bands):
            if band.center_freq > 2000:
                adapted_gains[i] += 1.0

    elif spectral_centroid > 4000:  # Bright content
        # Reduce treble to avoid harshness
        for i, band in enumerate(critical_bands):
            if band.center_freq > 4000:
                adapted_gains[i] -= 0.5

    return adapted_gains


def create_target_curve(genre: Optional[str] = None,
                       brightness: float = 0.0,
                       warmth: float = 0.0,
                       num_bands: int = 25) -> np.ndarray:
    """
    Create custom target EQ curve

    Args:
        genre: Optional genre for base curve
        brightness: Brightness adjustment (-1.0 to 1.0)
        warmth: Warmth adjustment (-1.0 to 1.0)
        num_bands: Number of frequency bands

    Returns:
        Target EQ curve
    """
    # Start with genre curve or flat
    if genre:
        curve = generate_genre_eq_curve(genre, num_bands)
    else:
        curve = np.zeros(num_bands)

    # Apply brightness adjustment (affects high frequencies)
    if brightness != 0:
        for i in range(num_bands):
            # More effect on higher bands
            high_freq_factor = i / num_bands
            curve[i] += brightness * 2.0 * high_freq_factor

    # Apply warmth adjustment (affects mid-low frequencies)
    if warmth != 0:
        for i in range(num_bands):
            # More effect on mid-low bands
            mid_low_factor = 1.0 - abs(i / num_bands - 0.3)
            curve[i] += warmth * 2.0 * mid_low_factor

    return curve
