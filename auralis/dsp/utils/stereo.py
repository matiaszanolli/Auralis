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

    # Guard: constant/silent channels have zero variance — np.corrcoef returns NaN.
    # Treat them as perfectly correlated (mono) → width = 0.0 (fixes #2611).
    if np.std(left) < 1e-9 or np.std(right) < 1e-9:
        return 0.0

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
    sample_rate: int = 44100,
    original_width: float = 0.5,
    bass_content: float = 0.3
) -> np.ndarray:
    """
    Adjust stereo width with frequency-dependent processing.

    Uses PARALLEL processing to avoid crossover phase/magnitude issues.
    Instead of splitting bands and recombining (which causes notches with
    filtfilt), we extract each band, widen it, and ADD the difference
    on top of the original signal. This preserves flat frequency response.

    Frequency bands:
    - Lows (<300Hz): No expansion - keeps bass/kick centered and punchy
    - Low-mids (300-2kHz): Gentle expansion - body and warmth
    - High-mids (2k-8kHz): Moderate expansion - presence, guitars
    - Highs (>8kHz): Full expansion - air, cymbals

    Args:
        stereo_audio: Stereo audio signal [samples, 2]
        width_factor: Base width factor (0.5 = no change, 1.0 = max width)
        sample_rate: Audio sample rate
        original_width: Unused (kept for API compatibility)
        bass_content: Unused (kept for API compatibility)

    Returns:
        Width-adjusted stereo audio with frequency-appropriate widening
    """
    if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
        return stereo_audio

    # No change needed
    if abs(width_factor - 0.5) < 0.01:
        return stereo_audio

    nyquist = sample_rate / 2

    # Band extraction frequencies (using simple Butterworth, not LR4)
    # We only need to extract bands, not split perfectly
    freq_lowmid_lo = min(0.99, max(0.01, 300.0 / nyquist))
    freq_lowmid_hi = min(0.99, max(0.01, 2000.0 / nyquist))
    freq_highmid_lo = min(0.99, max(0.01, 2000.0 / nyquist))
    freq_highmid_hi = min(0.99, max(0.01, 8000.0 / nyquist))
    freq_high = min(0.99, max(0.01, 8000.0 / nyquist))

    # Simple bandpass filters for extraction (order 2 is gentle enough)
    sos_lowmid = butter(2, [freq_lowmid_lo, freq_lowmid_hi], btype='band', output='sos')
    sos_highmid = butter(2, [freq_highmid_lo, freq_highmid_hi], btype='band', output='sos')
    sos_high = butter(2, freq_high, btype='high', output='sos')

    # Extract bands (for width calculation only, not recombination)
    band_lowmid = sosfiltfilt(sos_lowmid, stereo_audio, axis=0)
    band_highmid = sosfiltfilt(sos_highmid, stereo_audio, axis=0)
    band_high = sosfiltfilt(sos_high, stereo_audio, axis=0)

    # Calculate expansion amount from base factor
    expansion = width_factor - 0.5  # 0 to 0.5 range

    # Frequency-dependent expansion factors
    # Lower frequencies get less expansion to avoid phase issues on cheap headphones
    f_min = 300.0
    f_max = 16000.0
    log_range = np.log(f_max / f_min)

    def expansion_factor(f_center: float) -> float:
        """Smooth logarithmic curve: higher freq = more expansion"""
        log_pos = np.log(f_center / f_min) / log_range  # 0.0 to 1.0
        return 0.3 + (log_pos * 0.7)  # Ramp from 0.3 to 1.0 with frequency

    # Width factors for each band
    width_lowmid = 0.5 + expansion * expansion_factor(775.0)    # ~0.6
    width_highmid = 0.5 + expansion * expansion_factor(4000.0)  # ~0.75
    width_high = 0.5 + expansion * expansion_factor(11314.0)    # ~0.95

    # Calculate widened versions of each band
    band_lowmid_w = adjust_stereo_width(band_lowmid, width_lowmid)
    band_highmid_w = adjust_stereo_width(band_highmid, width_highmid)
    band_high_w = adjust_stereo_width(band_high, width_high)

    # PARALLEL processing: add the WIDTH DIFFERENCE on top of original
    # This avoids crossover notches because we never split and recombine
    # diff = widened - original_band
    # result = original + diff = original + (widened - band) = original with added width
    diff_lowmid = band_lowmid_w - band_lowmid
    diff_highmid = band_highmid_w - band_highmid
    diff_high = band_high_w - band_high

    return stereo_audio + diff_lowmid + diff_highmid + diff_high
