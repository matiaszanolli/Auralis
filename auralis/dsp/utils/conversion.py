"""
Audio Conversion Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~

Conversion functions between different audio representations

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

# The silence convention used by the mastering pipeline's peak/headroom maths: the
# 16-bit noise floor. Everything else in the codebase reported silence as -inf
# (loudness meter, content analysis) or ~-200 dB (``to_db`` below), and the three
# disagreed (#5785). Callers say which they want via ``silence_db``; there is no
# implicit default other than -inf.
SILENCE_FLOOR_DB: float = -96.0


def amplitude_to_db(value: float, silence_db: float = -np.inf) -> float:
    """
    Convert a linear amplitude to dB: ``20 * log10(value)``, or ``silence_db`` when
    ``value`` is not positive (zero, negative, or NaN).

    The one scalar amplitude -> dB conversion. The silence convention is explicit
    (default ``-inf``; ``SILENCE_FLOOR_DB`` for the mastering headroom maths)
    instead of being re-decided at each of ~35 inline ``20 * np.log10`` sites.
    """
    return float(20 * np.log10(value)) if value > 0 else silence_db


def db_to_amplitude(db: float) -> float:
    """
    Convert dB to linear amplitude: ``10 ** (db / 20)`` — the exact inverse
    of :func:`amplitude_to_db` for positive values. The one definition
    (#6213); the ~29 inline ``10 ** (x / 20)`` sites it replaces were the
    re-entry point for the silence-convention disagreement #5785 removed.
    """
    return float(10 ** (db / 20))


def peak_db(audio: np.ndarray, silence_db: float = -np.inf) -> float:
    """Peak level of ``audio`` in dBFS (``silence_db`` if it is all zeros/empty-peak)."""
    return amplitude_to_db(np.max(np.abs(audio)), silence_db)


def rms_db(audio: np.ndarray, silence_db: float = -np.inf) -> float:
    """RMS level of ``audio`` in dBFS (``silence_db`` for digital silence)."""
    from ..basic import rms

    return amplitude_to_db(rms(audio), silence_db)


#: Amplitude epsilon / dB floor for array conversions (#6230). The scalar
#: to_db() below floors at the same value via max(); this named constant is
#: the one home for the ARRAY form's `+ eps` guard that #5785 left inline at
#: every call site. FingerprintConstants.EPSILON aliases it.
AMPLITUDE_EPS = 1e-10


def amplitude_to_db_array(x: "np.ndarray | float") -> "np.ndarray":
    """20*log10(x + AMPLITUDE_EPS) over an array — the guarded array form of
    to_db() (#5785 unified the scalar half; #6230 the array half). Returns
    float64 for float32 input, like any log-scale conversion."""
    return 20 * np.log10(np.asarray(x, dtype=float) + AMPLITUDE_EPS)

#: RMS/std level below which a channel counts as digital silence for the
#: stereo-correlation guard (#6230) — shared by dsp/utils/stereo.py and
#: core/processing/stage_snapshot.py, which used to type it twice.
SILENCE_STD_THRESHOLD = 1e-9
