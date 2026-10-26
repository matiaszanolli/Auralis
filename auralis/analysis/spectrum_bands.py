"""
FFT-bin to frequency-band membership, shared by band mapping and by anything
that needs to know which bands the FFT actually resolved.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np


def band_masks(frequencies: np.ndarray, frequency_bins: np.ndarray) -> list[np.ndarray]:
    """One boolean mask over ``frequencies`` per band.

    Band ``i`` covers ``[frequency_bins[i], frequency_bins[i + 1])``; the last
    band is open-ended upward.
    """
    edges = np.append(frequency_bins, np.inf)
    return [(frequencies >= edges[i]) & (frequencies < edges[i + 1]) for i in range(len(frequency_bins))]


def populated_band_mask(frequencies: np.ndarray, frequency_bins: np.ndarray) -> np.ndarray:
    """True for each band that contains at least one FFT bin.

    Narrow low bands fall between two bins (an 8192-point FFT at 44.1 kHz has
    5.4 Hz resolution against bands ~1 Hz wide at 20 Hz). Such a band measures
    nothing, so it must not be scored (#5745).
    """
    return np.array([bool(np.any(m)) for m in band_masks(frequencies, frequency_bins)], dtype=bool)
