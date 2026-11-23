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


def _dc_block_sos(sample_rate: float) -> np.ndarray:
    return np.asarray(butter(2, normalized_corner(DC_BLOCK_CUTOFF_HZ, sample_rate), btype="highpass", output="sos"))


def remove_dc(audio: np.ndarray, sample_rate: float) -> np.ndarray:
    """*audio* (samples[, channels]) high-passed at DC_BLOCK_CUTOFF_HZ; a new array, same shape and dtype."""
    return np.asarray(sosfilt(_dc_block_sos(sample_rate), audio, axis=0), dtype=audio.dtype)


def remove_dc_dual_mono(mono: np.ndarray, sample_rate: float) -> np.ndarray:
    """``remove_dc(np.column_stack([mono, mono]))`` without building that stacked input (#6717).

    The channel is filtered once and written to both. The result matches
    remove_dc's in values and in memory layout too: sosfilt along axis 0 hands
    back the transpose of a (channels, samples) array, and later whole-buffer
    reductions sum in memory order.
    """
    filtered = np.asarray(sosfilt(_dc_block_sos(sample_rate), mono), dtype=mono.dtype)
    out = np.empty((2, len(mono)), dtype=mono.dtype)
    out[0] = filtered
    out[1] = filtered
    return out.T
