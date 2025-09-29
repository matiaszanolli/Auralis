# -*- coding: utf-8 -*-

"""
Unified DSP System
~~~~~~~~~~~~~~~~~

Merged DSP functions from Matchering and Auralis for adaptive processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Combined from Matchering 2.0 by Sergree and Auralis enhancements
"""

import numpy as np
from typing import Tuple, Optional, Union
from .basic import rms, normalize, amplify, mid_side_encode, mid_side_decode


# Core audio utilities (enhanced from both systems)
def size(audio: np.ndarray) -> int:
    """Get the number of audio samples"""
    return audio.shape[0]


def channel_count(audio: np.ndarray) -> int:
    """Get the number of audio channels"""
    if audio.ndim == 1:
        return 1
    return audio.shape[1]


def is_mono(audio: np.ndarray) -> bool:
    """Check if audio is mono"""
    return channel_count(audio) == 1


def is_stereo(audio: np.ndarray) -> bool:
    """Check if audio is stereo"""
    return channel_count(audio) == 2


def mono_to_stereo(audio: np.ndarray) -> np.ndarray:
    """Convert mono audio to stereo"""
    if audio.ndim == 1:
        return np.column_stack([audio, audio])
    return np.repeat(audio, repeats=2, axis=1)


# Enhanced from Matchering
def count_max_peaks(audio: np.ndarray) -> Tuple[float, int]:
    """Count maximum peaks in audio signal"""
    max_value = np.abs(audio).max()
    return max_value, np.sum(np.abs(audio) >= max_value * 0.99)


def clip(audio: np.ndarray, ceiling: float = 1.0) -> np.ndarray:
    """Clip audio signal to prevent clipping"""
    return np.clip(audio, -ceiling, ceiling)


def to_db(linear_value: float) -> float:
    """Convert linear value to decibels"""
    return 20 * np.log10(max(linear_value, 1e-10))


def from_db(db_value: float) -> float:
    """Convert decibels to linear value"""
    return 10 ** (db_value / 20)


# Advanced DSP functions for adaptive processing
def spectral_centroid(audio: np.ndarray, sample_rate: int = 44100) -> float:
    """
    Calculate spectral centroid (brightness measure)

    Args:
        audio: Input audio signal
        sample_rate: Sample rate in Hz

    Returns:
        Spectral centroid in Hz
    """
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Use a window to focus on the middle part of the signal
    if len(audio) > 4096:
        start = len(audio) // 4
        end = 3 * len(audio) // 4
        audio_segment = audio[start:end]
        # Use a power-of-2 size for FFT efficiency
        fft_size = min(4096, len(audio_segment))
        audio_segment = audio_segment[:fft_size]
    else:
        audio_segment = audio

    # Apply window to reduce spectral leakage
    window = np.hanning(len(audio_segment))
    windowed_audio = audio_segment * window

    # Compute magnitude spectrum
    fft = np.fft.rfft(windowed_audio)
    magnitude = np.abs(fft)

    # Frequency bins
    freqs = np.linspace(0, sample_rate // 2, len(magnitude))

    # Calculate centroid
    if np.sum(magnitude) > 1e-10:
        centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
    else:
        centroid = sample_rate // 4  # Default to quarter of sample rate

    return centroid


def spectral_rolloff(audio: np.ndarray, sample_rate: int = 44100,
                    rolloff_percent: float = 0.85) -> float:
    """
    Calculate spectral rolloff frequency

    Args:
        audio: Input audio signal
        sample_rate: Sample rate in Hz
        rolloff_percent: Percentage of energy for rolloff calculation

    Returns:
        Rolloff frequency in Hz
    """
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Compute magnitude spectrum
    fft = np.fft.rfft(audio)
    magnitude = np.abs(fft) ** 2  # Power spectrum

    # Frequency bins
    freqs = np.linspace(0, sample_rate // 2, len(magnitude))

    # Calculate rolloff
    total_energy = np.sum(magnitude)
    if total_energy > 0:
        cumulative_energy = np.cumsum(magnitude)
        rolloff_threshold = rolloff_percent * total_energy
        rolloff_idx = np.where(cumulative_energy >= rolloff_threshold)[0]
        if len(rolloff_idx) > 0:
            return freqs[rolloff_idx[0]]

    return sample_rate // 2  # Default to Nyquist frequency


def zero_crossing_rate(audio: np.ndarray) -> float:
    """
    Calculate zero crossing rate

    Args:
        audio: Input audio signal

    Returns:
        Zero crossing rate (0-1)
    """
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Count zero crossings
    zero_crossings = np.sum(np.diff(np.sign(audio)) != 0)
    return zero_crossings / (2 * len(audio))


def crest_factor(audio: np.ndarray) -> float:
    """
    Calculate crest factor (peak-to-RMS ratio)

    Args:
        audio: Input audio signal

    Returns:
        Crest factor in dB
    """
    peak = np.max(np.abs(audio))
    rms_value = rms(audio)

    if rms_value > 0:
        return to_db(peak / rms_value)
    else:
        return 0.0


def energy_profile(audio: np.ndarray, window_size: int = 1024) -> np.ndarray:
    """
    Calculate energy profile of audio signal

    Args:
        audio: Input audio signal
        window_size: Size of analysis window

    Returns:
        Array of energy values over time
    """
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Calculate energy in overlapping windows
    hop_size = window_size // 2
    energy_values = []

    for i in range(0, len(audio) - window_size, hop_size):
        window = audio[i:i + window_size]
        energy = np.sum(window ** 2)
        energy_values.append(energy)

    return np.array(energy_values)


def tempo_estimate(audio: np.ndarray, sample_rate: int = 44100) -> float:
    """
    Rough tempo estimation using onset detection

    Args:
        audio: Input audio signal
        sample_rate: Sample rate in Hz

    Returns:
        Estimated tempo in BPM
    """
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Simple onset detection using spectral flux
    window_size = 1024
    hop_size = 512

    # Calculate spectral flux
    flux_values = []
    prev_spectrum = None

    for i in range(0, len(audio) - window_size, hop_size):
        window = audio[i:i + window_size]
        spectrum = np.abs(np.fft.rfft(window))

        if prev_spectrum is not None:
            flux = np.sum(np.maximum(0, spectrum - prev_spectrum))
            flux_values.append(flux)

        prev_spectrum = spectrum

    if len(flux_values) < 2:
        return 120.0  # Default tempo

    # Find peaks in flux (rough onset detection)
    flux_array = np.array(flux_values)
    mean_flux = np.mean(flux_array)
    std_flux = np.std(flux_array)
    threshold = mean_flux + 0.5 * std_flux

    peaks = []
    for i in range(1, len(flux_array) - 1):
        if (flux_array[i] > flux_array[i-1] and
            flux_array[i] > flux_array[i+1] and
            flux_array[i] > threshold):
            peaks.append(i)

    if len(peaks) < 2:
        return 120.0  # Default tempo

    # Calculate average interval between peaks
    intervals = np.diff(peaks)
    if len(intervals) > 0:
        avg_interval = np.mean(intervals)
        # Convert to BPM
        time_per_hop = hop_size / sample_rate
        beat_interval = avg_interval * time_per_hop
        if beat_interval > 0:
            bpm = 60.0 / beat_interval
            # Constrain to reasonable range
            return np.clip(bpm, 60, 200)

    return 120.0  # Default tempo


# Adaptive processing utilities
def adaptive_gain_calculation(target_rms: float, reference_rms: float,
                            adaptation_factor: float = 0.8) -> float:
    """
    Calculate adaptive gain with smoother transitions

    Args:
        target_rms: RMS of target signal
        reference_rms: RMS of reference or target level
        adaptation_factor: How aggressively to adapt (0-1)

    Returns:
        Gain factor (linear)
    """
    if target_rms > 0:
        raw_gain = reference_rms / target_rms

        # Special case: if adaptation_factor is 1.0, return raw gain
        if adaptation_factor >= 0.99:
            return np.clip(raw_gain, 0.1, 10.0)

        # Apply adaptation factor for smoother transitions
        # adaptation_factor of 0.8 means 80% of the way to the target
        gain = 1.0 + (raw_gain - 1.0) * adaptation_factor

        # Limit gain to reasonable range
        return np.clip(gain, 0.1, 10.0)
    return 1.0


def psychoacoustic_weighting(frequencies: np.ndarray) -> np.ndarray:
    """
    Apply psychoacoustic weighting to frequency spectrum

    Args:
        frequencies: Array of frequency values in Hz

    Returns:
        Weighting factors for each frequency
    """
    # Simplified A-weighting-like curve
    weights = np.ones_like(frequencies)

    for i, freq in enumerate(frequencies):
        if freq < 20:
            weights[i] = 0.1  # Very low frequencies
        elif freq < 100:
            weights[i] = 0.5  # Low frequencies
        elif freq < 1000:
            weights[i] = 0.8  # Mid-low frequencies
        elif freq < 4000:
            weights[i] = 1.0  # Most important range
        elif freq < 8000:
            weights[i] = 0.9  # High frequencies
        elif freq < 16000:
            weights[i] = 0.7  # Very high frequencies
        else:
            weights[i] = 0.3  # Ultrasonic

    return weights


def smooth_parameter_transition(current_value: float, target_value: float,
                               smoothing_factor: float = 0.1) -> float:
    """
    Smooth parameter transitions to avoid artifacts

    Args:
        current_value: Current parameter value
        target_value: Target parameter value
        smoothing_factor: Speed of transition (0-1)

    Returns:
        Smoothed parameter value
    """
    return current_value + (target_value - current_value) * smoothing_factor


def calculate_loudness_units(audio: np.ndarray, sample_rate: int = 44100) -> float:
    """
    Simple loudness calculation (approximation of LUFS)

    Args:
        audio: Input audio signal
        sample_rate: Sample rate in Hz

    Returns:
        Loudness in approximate LUFS
    """
    if audio.ndim == 1:
        audio = mono_to_stereo(audio)

    # Simple K-weighting approximation
    # This is a simplified version - real LUFS calculation is more complex
    rms_value = rms(audio)
    if rms_value > 0:
        loudness_db = to_db(rms_value)
        # Rough conversion to LUFS-like scale
        lufs_approx = loudness_db - 23.0  # Offset to approximate LUFS scale
        return lufs_approx
    else:
        return -70.0  # Very quiet


# Stereo processing utilities
def stereo_width_analysis(stereo_audio: np.ndarray) -> float:
    """
    Analyze stereo width of audio signal

    Args:
        stereo_audio: Stereo audio signal [samples, 2]

    Returns:
        Stereo width factor (0-1, where 0.5 is normal stereo)
    """
    if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
        return 0.5  # Default for non-stereo

    left = stereo_audio[:, 0]
    right = stereo_audio[:, 1]

    # Calculate correlation
    correlation = np.corrcoef(left, right)[0, 1]

    # Convert correlation to width (inverse relationship)
    width = 1.0 - np.abs(correlation)

    return np.clip(width, 0.0, 1.0)


def adjust_stereo_width(stereo_audio: np.ndarray, width_factor: float) -> np.ndarray:
    """
    Adjust stereo width of audio signal

    Args:
        stereo_audio: Stereo audio signal [samples, 2]
        width_factor: Width adjustment (0.5 = normal, <0.5 = narrower, >0.5 = wider)

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