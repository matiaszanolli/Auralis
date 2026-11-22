"""
FFT-bin to frequency-band membership, shared by band mapping and by anything
that needs to know which bands the FFT actually resolved.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np


def band_index(frequencies: np.ndarray, frequency_bins: np.ndarray) -> np.ndarray:
    """The band each of ``frequencies`` falls in, or -1 below the first band.

    Band ``i`` covers ``[frequency_bins[i], frequency_bins[i + 1])``; the last
    band is open-ended upward. ``frequency_bins`` must be ascending.

    One ``searchsorted`` pass instead of a boolean mask per band: band mapping
    runs once per analysis frame, and building 64-128 masks over every FFT bin
    each frame was most of ``SpectrumAnalyzer``'s cost.
    """
    return np.searchsorted(frequency_bins, frequencies, side='right') - 1


def populated_band_mask(frequencies: np.ndarray, frequency_bins: np.ndarray) -> np.ndarray:
    """True for each band that contains at least one FFT bin.

    Narrow low bands fall between two bins (an 8192-point FFT at 44.1 kHz has
    5.4 Hz resolution against bands ~1 Hz wide at 20 Hz). Such a band measures
    nothing, so it must not be scored (#5745).
    """
    index = band_index(frequencies, frequency_bins)
    return np.bincount(index[index >= 0], minlength=len(frequency_bins)) > 0
