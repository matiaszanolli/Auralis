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


def _linkwitz_riley_4(freq: float, btype: str) -> np.ndarray:
    """
    Create 4th-order Linkwitz-Riley filter (LR4, 24dB/octave).

    LR4 filters are two cascaded 2nd-order Butterworth filters.
    They have -6dB at crossover and sum flat when combined.
    """
    # Two cascaded 2nd-order Butterworth = LR4
    sos1 = butter(2, freq, btype=btype, output='sos')
    sos2 = butter(2, freq, btype=btype, output='sos')
    return np.vstack([sos1, sos2])


def adjust_stereo_width_multiband(
    stereo_audio: np.ndarray,
    width_factor: float,
    sample_rate: int = 44100
) -> np.ndarray:
    """
    Adjust stereo width with frequency-dependent processing.

    Uses Linkwitz-Riley crossovers (LR4, 24dB/octave) for phase-coherent
    band splitting that sums flat. Expansion increases smoothly from
    bass to highs.

    Frequency bands:
    - Lows (<300Hz): No expansion - keeps bass/kick centered and punchy
    - Low-mids (300-2kHz): Gradual expansion - body and warmth
    - High-mids (2k-8kHz): Full expansion - presence, guitars
    - Highs (>8kHz): Full expansion - air, cymbals

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

    # Crossover frequencies for LR4 splits
    # 300Hz: preserves kick/bass fundamentals and first harmonics
    # 2kHz: presence/vocal range boundary
    # 8kHz: air/brilliance boundary
    freq_low = min(0.99, max(0.01, 300.0 / nyquist))
    freq_mid = min(0.99, max(0.01, 2000.0 / nyquist))
    freq_high = min(0.99, max(0.01, 8000.0 / nyquist))

    # LR4 crossover filters (24dB/octave, sums flat)
    sos_lp_low = _linkwitz_riley_4(freq_low, 'low')
    sos_hp_low = _linkwitz_riley_4(freq_low, 'high')
    sos_lp_mid = _linkwitz_riley_4(freq_mid, 'low')
    sos_hp_mid = _linkwitz_riley_4(freq_mid, 'high')
    sos_lp_high = _linkwitz_riley_4(freq_high, 'low')
    sos_hp_high = _linkwitz_riley_4(freq_high, 'high')

    # Split into 4 bands using proper LR4 crossover topology
    # Band 1: < 300Hz (low-pass at 300)
    band_low = sosfiltfilt(sos_lp_low, stereo_audio, axis=0)

    # Band 2: 300-2kHz (high-pass at 300, then low-pass at 2k)
    temp = sosfiltfilt(sos_hp_low, stereo_audio, axis=0)
    band_lowmid = sosfiltfilt(sos_lp_mid, temp, axis=0)

    # Band 3: 2k-8kHz (high-pass at 2k, then low-pass at 8k)
    temp = sosfiltfilt(sos_hp_mid, stereo_audio, axis=0)
    band_highmid = sosfiltfilt(sos_lp_high, temp, axis=0)

    # Band 4: > 8kHz (high-pass at 8k)
    band_high = sosfiltfilt(sos_hp_high, stereo_audio, axis=0)

    # Calculate expansion amount from base factor
    expansion = width_factor - 0.5  # 0 to 0.5 range

    # Smooth, balanced expansion curve
    # Lows: 0% - centered for punch
    # Low-mids: 70% - preserve warmth while adding width
    # High-mids: 100% - full expansion for presence
    # Highs: 100% - full expansion for air (no extra boost)
    width_low = 0.5
    width_lowmid = 0.5 + expansion * 0.7
    width_highmid = 0.5 + expansion * 1.0
    width_high = 0.5 + expansion * 1.0

    # Apply width to each band
    band_lowmid_w = adjust_stereo_width(band_lowmid, width_lowmid)
    band_highmid_w = adjust_stereo_width(band_highmid, width_highmid)
    band_high_w = adjust_stereo_width(band_high, width_high)

    # Recombine - LR4 crossovers sum to unity
    return band_low + band_lowmid_w + band_highmid_w + band_high_w
