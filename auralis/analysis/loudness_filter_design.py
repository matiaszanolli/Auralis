"""
BS.1770-4 K-weighting filter design (split from loudness_filters.py, #5593): the two
biquads derived from the standard's analog prototypes by the bilinear transform, which
reproduces its tabulated 48 kHz coefficients exactly and extends them to any rate.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

# BS.1770-4 Annex 1 filter parameters, the values the 48 kHz tables in the standard were
# derived from (also what pyloudnorm and ffmpeg's ebur128 use).
_SHELF_GAIN_DB = 3.999843853973347
_SHELF_Q = 0.7071752369554196
_SHELF_FC_HZ = 1681.9744509555319
_RLB_Q = 0.5003270373253953
_RLB_FC_HZ = 38.13547087613982


def head_shelf(fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Stage-1 high-shelf biquad (+4 dB above ~1.7 kHz), normalised to a0 = 1."""
    k = np.tan(np.pi * _SHELF_FC_HZ / fs)
    vh = 10 ** (_SHELF_GAIN_DB / 20)
    vb = vh ** 0.4996667741545416
    a0 = 1 + k / _SHELF_Q + k * k
    b = np.array([vh + vb * k / _SHELF_Q + k * k, 2 * (k * k - vh), vh - vb * k / _SHELF_Q + k * k]) / a0
    a = np.array([1.0, 2 * (k * k - 1) / a0, (1 - k / _SHELF_Q + k * k) / a0])
    return b, a


def rlb_highpass(fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Stage-2 RLB high-pass: a double zero at DC and Q ~ 0.5003 (not a Butterworth 0.707)."""
    k = np.tan(np.pi * _RLB_FC_HZ / fs)
    a0 = 1 + k / _RLB_Q + k * k
    return np.array([1.0, -2.0, 1.0]), np.array([1.0, 2 * (k * k - 1) / a0, (1 - k / _RLB_Q + k * k) / a0])
