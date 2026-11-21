"""
Interpolation Helpers
~~~~~~~~~~~~~~~~~~~~~

Vectorized interpolation and envelope creation utilities for DSP operations

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


import numpy as np


def create_mel_triangular_filters(n_filters: int, n_fft: int,
                                  sample_rate: int) -> list[np.ndarray]:
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
