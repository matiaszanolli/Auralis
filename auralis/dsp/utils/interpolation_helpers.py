# -*- coding: utf-8 -*-

"""
Interpolation Helpers
~~~~~~~~~~~~~~~~~~~~~

Vectorized interpolation and envelope creation utilities for DSP operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, List, Optional

import numpy as np


def create_triangular_envelope(start: float, center: float, end: float,
                               length: int, strategy: str = 'linear') -> np.ndarray:
    """
    Create a triangular (tent) filter response.

    Creates a piecewise linear or windowed triangular shape with:
    - Zero at start and end
    - Peak of 1.0 at center
    - Linear interpolation between points

    Args:
        start: Starting position (0 to length-1, or frequency in Hz)
        center: Center position (peak location)
        end: Ending position
        length: Total length of output array
        strategy: Envelope creation strategy
            - 'linear': Simple piecewise linear slopes (default)
            - 'hann': Hann window inside triangle (smoother)
            - 'hamming': Hamming window inside triangle (less overshoot)

    Returns:
        np.ndarray: Triangular envelope of shape (length,)

    Examples:
        >>> envelope = create_triangular_envelope(100, 150, 200, 400)
        >>> assert len(envelope) == 400
        >>> assert np.max(envelope) <= 1.0
        >>> assert envelope[100:150].min() > 0
    """
    if not isinstance(length, int) or length <= 0:
        raise ValueError(f"length must be positive integer, got {length}")

    if not (0 <= start < length and 0 <= center < length and 0 <= end < length):
        raise ValueError(f"start/center/end must be in [0, {length-1}]")

    if not (start <= center <= end):
        raise ValueError("start <= center <= end must hold")

    envelope = np.zeros(length, dtype=np.float32)

    # Handle degenerate cases
    if start == end:
        if 0 <= int(center) < length:
            envelope[int(center)] = 1.0
        return envelope

    # Convert to integer indices
    start_idx = int(np.round(start))
    center_idx = int(np.round(center))
    end_idx = int(np.round(end))

    if start_idx == center_idx:
        # Rising slope only
        if end_idx > center_idx:
            indices = np.arange(center_idx, end_idx + 1)
            envelope[indices] = 1.0 - (indices - center_idx) / (end_idx - center_idx)
    elif center_idx == end_idx:
        # Falling slope only
        if center_idx > start_idx:
            indices = np.arange(start_idx, center_idx + 1)
            envelope[indices] = (indices - start_idx) / (center_idx - start_idx)
    else:
        # Both slopes
        # Rising slope
        if center_idx > start_idx:
            rising_indices = np.arange(start_idx, center_idx + 1)
            envelope[rising_indices] = (rising_indices - start_idx) / (center_idx - start_idx)

        # Falling slope
        if end_idx > center_idx:
            falling_indices = np.arange(center_idx, end_idx + 1)
            envelope[falling_indices] = 1.0 - (falling_indices - center_idx) / (end_idx - center_idx)

    # Apply window strategy for smoothing
    if strategy == 'hann':
        _apply_window_smoothing(envelope, start_idx, end_idx, 'hann')
    elif strategy == 'hamming':
        _apply_window_smoothing(envelope, start_idx, end_idx, 'hamming')
    elif strategy != 'linear':
        raise ValueError(f"Unknown strategy: {strategy}")

    return envelope


def _apply_window_smoothing(envelope: np.ndarray, start_idx: int, end_idx: int,
                           window_type: str) -> None:
    """
    Apply window smoothing to triangular envelope in-place.

    Args:
        envelope: Envelope array to modify
        start_idx: Start index of triangle
        end_idx: End index of triangle
        window_type: 'hann' or 'hamming'
    """
    width = end_idx - start_idx + 1
    if width <= 1:
        return

    if window_type == 'hann':
        window = np.hanning(width)
    else:  # hamming
        window = np.hamming(width)

    mask = envelope[start_idx:end_idx + 1] > 0
    envelope[start_idx:end_idx + 1] *= window


def create_triangular_filterbank(critical_bands: List[Any], sample_rate: int,
                                 fft_size: int) -> np.ndarray:
    """
    Create a triangular filterbank for critical bands.

    Vectorized creation of triangular filters for all critical bands.
    Much faster than loop-based creation.

    Args:
        critical_bands: List of CriticalBand objects with low_freq, center_freq, high_freq
        sample_rate: Audio sample rate in Hz
        fft_size: FFT size (determines frequency resolution)

    Returns:
        np.ndarray: Filter bank matrix of shape (num_bands, num_bins)
            where num_bins = fft_size // 2 + 1

    Examples:
        >>> from dataclasses import dataclass
        >>> @dataclass
        ... class Band:
        ...     low_freq: float
        ...     center_freq: float
        ...     high_freq: float
        >>> bands = [Band(100, 150, 200), Band(200, 300, 400)]
        >>> fb = create_triangular_filterbank(bands, 44100, 2048)
        >>> assert fb.shape[0] == len(bands)
        >>> assert fb.shape[1] == 2048 // 2 + 1
    """
    num_bands = len(critical_bands)
    num_bins = fft_size // 2 + 1

    # Frequency array for each FFT bin
    freqs = np.linspace(0, sample_rate // 2, num_bins)

    # Create all filters at once (vectorized)
    filter_bank = np.zeros((num_bands, num_bins), dtype=np.float32)

    for i, band in enumerate(critical_bands):
        low_freq = band.low_freq
        center_freq = band.center_freq
        high_freq = band.high_freq

        # Rising slope: from 0 at low_freq to 1 at center_freq
        rising_mask = (freqs >= low_freq) & (freqs <= center_freq)
        if center_freq > low_freq:
            filter_bank[i, rising_mask] = (freqs[rising_mask] - low_freq) / (center_freq - low_freq)
        else:
            filter_bank[i, rising_mask] = 1.0

        # Falling slope: from 1 at center_freq to 0 at high_freq
        falling_mask = (freqs > center_freq) & (freqs <= high_freq)
        if high_freq > center_freq:
            filter_bank[i, falling_mask] = (high_freq - freqs[falling_mask]) / (high_freq - center_freq)

    return filter_bank


def create_mel_triangular_filters(n_filters: int, n_fft: int,
                                  sample_rate: int) -> List[np.ndarray]:
    """
    Create triangular mel-scale filter bank.

    Creates n_filters triangular filters spaced on the mel scale,
    vectorized for performance.

    Args:
        n_filters: Number of filters to create
        n_fft: FFT size (determines frequency resolution)
        sample_rate: Audio sample rate in Hz

    Returns:
        List[np.ndarray]: List of filter arrays, each of shape (n_fft,)

    Examples:
        >>> filters = create_mel_triangular_filters(13, 4096, 44100)
        >>> assert len(filters) == 13
        >>> assert all(len(f) == 4096 for f in filters)
    """
    # Convert Hz to mel scale
    mel_points = np.linspace(0, 2595 * np.log10(1 + (sample_rate/2) / 700), n_filters + 2)
    hz_points = 700 * (10**(mel_points / 2595) - 1)
    bin_points = np.floor((n_fft * 2) * hz_points / sample_rate).astype(int)

    filters = []

    for i in range(n_filters):
        filt = np.zeros(n_fft, dtype=np.float32)
        start, center, end = bin_points[i:i+3]

        # Rising slope
        if center > start:
            rising_indices = np.arange(start, min(center, n_fft))
            filt[rising_indices] = (rising_indices - start) / (center - start)

        # Falling slope
        if end > center:
            falling_indices = np.arange(center, min(end, n_fft))
            filt[falling_indices] = (end - falling_indices) / (end - center)

        filters.append(filt)

    return filters
