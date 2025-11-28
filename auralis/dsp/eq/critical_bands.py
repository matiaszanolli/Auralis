# -*- coding: utf-8 -*-

"""
Critical Band Calculations
~~~~~~~~~~~~~~~~~~~~~~~~~~

Bark scale critical band definitions and frequency mapping

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import List
from dataclasses import dataclass


@dataclass
class CriticalBand:
    """Critical band definition based on Bark scale"""
    index: int
    center_freq: float
    low_freq: float
    high_freq: float
    bandwidth: float
    weight: float  # Perceptual importance weight


def create_critical_bands() -> List[CriticalBand]:
    """
    Create critical bands based on Bark scale

    Returns:
        List of 25 critical bands covering 0-20kHz
    """
    # Bark scale critical band boundaries (approximate)
    bark_frequencies = [
        0, 100, 200, 300, 400, 510, 630, 770, 920, 1080,
        1270, 1480, 1720, 2000, 2320, 2700, 3150, 3700, 4400,
        5300, 6400, 7700, 9500, 12000, 15500, 20000
    ]

    critical_bands = []

    for i in range(len(bark_frequencies) - 1):
        low_freq = bark_frequencies[i]
        high_freq = bark_frequencies[i + 1]
        center_freq = np.sqrt(low_freq * high_freq)  # Geometric mean
        bandwidth = high_freq - low_freq

        # Perceptual weighting based on equal loudness contours
        weight = _calculate_perceptual_weight(center_freq)

        band = CriticalBand(
            index=i,
            center_freq=center_freq,
            low_freq=low_freq,
            high_freq=high_freq,
            bandwidth=bandwidth,
            weight=weight
        )
        critical_bands.append(band)

    return critical_bands


def _calculate_perceptual_weight(center_freq: float) -> float:
    """
    Calculate perceptual importance weight for a frequency

    Based on equal loudness contours (Fletcher-Munson curves)

    Args:
        center_freq: Center frequency in Hz

    Returns:
        Perceptual weight (0.3 to 1.0)
    """
    if 1000 <= center_freq <= 4000:
        return 1.0  # Most important frequency range (speech/presence)
    elif 300 <= center_freq <= 8000:
        return 0.8  # Important range
    elif 100 <= center_freq <= 300 or 8000 <= center_freq <= 16000:
        return 0.6  # Moderately important
    else:
        return 0.3  # Less important (extreme lows/highs)


def create_perceptual_weighting(sample_rate: int, fft_size: int) -> np.ndarray:
    """
    Create perceptual weighting curve (A-weighting inspired).

    Uses vectorized np.select() for performance (~5-10x speedup vs loop).

    Args:
        sample_rate: Audio sample rate in Hz
        fft_size: FFT size for frequency resolution

    Returns:
        Array of perceptual weights for each FFT bin
    """
    freqs = np.linspace(0, sample_rate // 2, fft_size // 2 + 1)

    # Vectorized conditional application using np.select
    weights = np.select(
        [
            freqs < 20,
            (freqs >= 20) & (freqs < 100),
            (freqs >= 100) & (freqs < 1000),
            (freqs >= 1000) & (freqs < 4000),
            (freqs >= 4000) & (freqs < 8000),
            (freqs >= 8000) & (freqs < 16000),
            freqs >= 16000,
        ],
        [
            0.1,  # < 20 Hz
            0.3,  # 20-100 Hz
            0.7 + 0.3 * (freqs - 100) / 900,  # 100-1000 Hz (linear interpolation)
            1.0,  # 1000-4000 Hz (peak sensitivity)
            1.0 - 0.2 * (freqs - 4000) / 4000,  # 4000-8000 Hz
            0.8 - 0.4 * (freqs - 8000) / 8000,  # 8000-16000 Hz
            0.4 - 0.3 * np.minimum((freqs - 16000) / 4000, 1.0),  # >= 16000 Hz
        ],
        default=1.0
    )

    return weights


def create_frequency_mapping(critical_bands: List[CriticalBand],
                            sample_rate: int,
                            fft_size: int) -> np.ndarray:
    """
    Map FFT bins to critical bands.

    Uses vectorized np.searchsorted() for O(n log m) complexity
    instead of O(n*m) loop-based approach. ~100-500x speedup for large sets.

    Args:
        critical_bands: List of critical bands
        sample_rate: Audio sample rate in Hz
        fft_size: FFT size

    Returns:
        Array mapping each FFT bin to a critical band index
    """
    freqs = np.linspace(0, sample_rate // 2, fft_size // 2 + 1)

    # Handle empty bands case
    if not critical_bands:
        return np.zeros(len(freqs), dtype=int)

    # Extract band edges for searchsorted
    band_edges = np.array([band.low_freq for band in critical_bands] +
                          [critical_bands[-1].high_freq])

    # Use searchsorted for O(log m) per frequency
    # searchsorted returns indices where frequencies would be inserted
    band_map = np.searchsorted(band_edges, freqs, side='right') - 1

    # Clamp to valid range [0, num_bands)
    band_map = np.clip(band_map, 0, len(critical_bands) - 1)

    return band_map
