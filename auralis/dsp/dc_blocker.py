"""
DC Blocker
~~~~~~~~~~

Removes a DC offset ahead of mastering (#5187). HybridProcessor had no DC stage
at all: an offset was scaled with the signal (0.01 in, ~0.026 out), so it spent
headroom, biased peak normalisation and loudness measurement, and stepped at
any boundary where the level changed.

A causal 2nd-order Butterworth high-pass at 5 Hz: below hearing, -0.02 dB at
20 Hz, ~7 degrees of phase at 60 Hz. Causal on purpose, so a chunk's output
depends only on audio before it: the streaming path renders every chunk after
the first with 5 s of preceding context, and the filter settles in well under
0.2 s, so independently rendered chunks agree at their seams.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
from scipy.signal import butter, sosfilt

from .utils.filters import normalized_corner

#: Corner of the DC-blocking high-pass. Above a 100 kHz sample rate the normalized
#: corner floor (filters.MIN_NORMALIZED_CORNER) moves it up, to ~9.6 Hz at 192 kHz.
DC_BLOCK_CUTOFF_HZ: float = 5.0


def remove_dc(audio: np.ndarray, sample_rate: float) -> np.ndarray:
    """*audio* (samples[, channels]) high-passed at DC_BLOCK_CUTOFF_HZ; a new array, same shape and dtype."""
    sos = butter(2, normalized_corner(DC_BLOCK_CUTOFF_HZ, sample_rate), btype="highpass", output="sos")
    return np.asarray(sosfilt(sos, audio, axis=0), dtype=audio.dtype)
