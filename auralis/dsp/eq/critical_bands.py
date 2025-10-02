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
    Create perceptual weighting curve (A-weighting inspired)

    Args:
        sample_rate: Audio sample rate in Hz
        fft_size: FFT size for frequency resolution

    Returns:
        Array of perceptual weights for each FFT bin
    """
    freqs = np.linspace(0, sample_rate // 2, fft_size // 2 + 1)
    weights = np.ones_like(freqs)

    for i, freq in enumerate(freqs):
        if freq < 20:
            weights[i] = 0.1
        elif freq < 100:
            weights[i] = 0.3
        elif freq < 1000:
            weights[i] = 0.7 + 0.3 * (freq - 100) / 900
        elif freq < 4000:
            weights[i] = 1.0  # Peak sensitivity
        elif freq < 8000:
            weights[i] = 1.0 - 0.2 * (freq - 4000) / 4000
        elif freq < 16000:
            weights[i] = 0.8 - 0.4 * (freq - 8000) / 8000
        else:
            weights[i] = 0.4 - 0.3 * min((freq - 16000) / 4000, 1.0)

    return weights


def create_frequency_mapping(critical_bands: List[CriticalBand],
                            sample_rate: int,
                            fft_size: int) -> np.ndarray:
    """
    Map FFT bins to critical bands

    Args:
        critical_bands: List of critical bands
        sample_rate: Audio sample rate in Hz
        fft_size: FFT size

    Returns:
        Array mapping each FFT bin to a critical band index
    """
    freqs = np.linspace(0, sample_rate // 2, fft_size // 2 + 1)
    band_map = np.zeros(len(freqs), dtype=int)

    for i, freq in enumerate(freqs):
        # Find the critical band for this frequency
        band_idx = 0
        for j, band in enumerate(critical_bands):
            if band.low_freq <= freq < band.high_freq:
                band_idx = j
                break
            elif freq >= band.high_freq:
                band_idx = j

        band_map[i] = min(band_idx, len(critical_bands) - 1)

    return band_map
