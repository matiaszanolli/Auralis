# -*- coding: utf-8 -*-

"""
Stereo Processing Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Utilities for stereo width analysis and manipulation

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from scipy.signal import butter, sosfiltfilt

from ..basic import mid_side_decode, mid_side_encode


def stereo_width_analysis(stereo_audio: np.ndarray) -> float:
    """
    Analyze stereo width of audio signal

    Calculates the stereo width based on the correlation between
    left and right channels.

    Args:
        stereo_audio: Stereo audio signal [samples, 2]

    Returns:
        Stereo width factor (0-1)
        - 0.0 = mono (identical channels)
        - 0.5 = normal stereo
        - 1.0 = maximum width (completely uncorrelated)
    """
    if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
        return 0.5  # Default for non-stereo

    left = stereo_audio[:, 0]
    right = stereo_audio[:, 1]

    # Calculate correlation
    correlation = np.corrcoef(left, right)[0, 1]

    # Convert correlation to width (inverse relationship)
    # correlation = 1.0 -> width = 0.0 (mono)
    # correlation = 0.0 -> width = 1.0 (maximum stereo)
    width = 1.0 - np.abs(correlation)

    return float(np.clip(width, 0.0, 1.0))


def adjust_stereo_width(stereo_audio: np.ndarray, width_factor: float) -> np.ndarray:
    """
    Adjust stereo width of audio signal

    Uses mid-side processing to adjust the stereo image width.

    Args:
        stereo_audio: Stereo audio signal [samples, 2]
        width_factor: Width adjustment factor
                     - 0.0 = mono
                     - 0.5 = normal stereo (no change)
                     - 1.0 = maximum width (doubled side signal)

    Returns:
        Width-adjusted stereo audio
    """
    if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
        return stereo_audio

    # Convert to mid-side
    mid, side = mid_side_encode(stereo_audio)

    # Adjust side component based on width factor
    # width_factor of 0.5 = no change, 0 = mono, 1 = maximum width
    side_gain = width_factor * 2.0
    adjusted_side = side * side_gain

    # Convert back to stereo
    return mid_side_decode(mid, adjusted_side)


def adjust_stereo_width_multiband(
    stereo_audio: np.ndarray,
    width_factor: float,
    sample_rate: int = 44100
) -> np.ndarray:
    """
    Adjust stereo width with frequency-dependent processing.

    Each frequency band gets appropriate width treatment:
    - Lows (<200Hz): No expansion - keeps kick/bass punchy and centered
    - Low-mids (200-2kHz): 50% of expansion - body and warmth
    - High-mids (2k-8kHz): 100% of expansion - presence, guitars
    - Highs (>8kHz): 120% of expansion - air, cymbals, sparkle

    Args:
        stereo_audio: Stereo audio signal [samples, 2]
        width_factor: Base width factor (0.5 = no change, 1.0 = max width)
        sample_rate: Audio sample rate

    Returns:
        Width-adjusted stereo audio with frequency-appropriate widening
    """
    if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
        return stereo_audio

    # No change needed
    if abs(width_factor - 0.5) < 0.01:
        return stereo_audio

    nyquist = sample_rate / 2

    # Crossover frequencies
    freq_low = 200.0 / nyquist      # Below: bass/kick (no expansion)
    freq_mid = 2000.0 / nyquist     # 200-2k: low-mids (partial expansion)
    freq_high = 8000.0 / nyquist    # 2k-8k: high-mids (full expansion)
                                     # Above 8k: highs (extra expansion)

    # Clamp to valid range
    freq_low = min(0.99, max(0.01, freq_low))
    freq_mid = min(0.99, max(0.01, freq_mid))
    freq_high = min(0.99, max(0.01, freq_high))

    # Design filters (2nd order Butterworth, zero-phase)
    sos_lp_low = butter(2, freq_low, btype='low', output='sos')
    sos_bp_lowmid = butter(2, [freq_low, freq_mid], btype='band', output='sos')
    sos_bp_highmid = butter(2, [freq_mid, freq_high], btype='band', output='sos')
    sos_hp_high = butter(2, freq_high, btype='high', output='sos')

    # Split into 4 bands
    band_low = sosfiltfilt(sos_lp_low, stereo_audio, axis=0)
    band_lowmid = sosfiltfilt(sos_bp_lowmid, stereo_audio, axis=0)
    band_highmid = sosfiltfilt(sos_bp_highmid, stereo_audio, axis=0)
    band_high = sosfiltfilt(sos_hp_high, stereo_audio, axis=0)

    # Calculate expansion amount from base factor
    # width_factor 0.5 = no change, 0.65 = +30% expansion
    expansion = width_factor - 0.5  # How much to expand (0 to 0.5)

    # Apply frequency-dependent width multipliers
    # Lows: 0% expansion (stay at 0.5)
    # Low-mids: 50% of requested expansion
    # High-mids: 100% of requested expansion
    # Highs: 120% of requested expansion (extra sparkle)
    width_low = 0.5                           # No change
    width_lowmid = 0.5 + expansion * 0.5      # Half expansion
    width_highmid = 0.5 + expansion * 1.0     # Full expansion
    width_high = 0.5 + min(0.5, expansion * 1.2)  # Extra expansion, capped

    # Apply width to each band
    # Low band stays untouched for punch
    band_lowmid_w = adjust_stereo_width(band_lowmid, width_lowmid)
    band_highmid_w = adjust_stereo_width(band_highmid, width_highmid)
    band_high_w = adjust_stereo_width(band_high, width_high)

    # Recombine all bands
    return band_low + band_lowmid_w + band_highmid_w + band_high_w
