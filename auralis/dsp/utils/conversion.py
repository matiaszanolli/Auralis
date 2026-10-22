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


def peak_db(audio: np.ndarray, silence_db: float = -np.inf) -> float:
    """Peak level of ``audio`` in dBFS (``silence_db`` if it is all zeros/empty-peak)."""
    return amplitude_to_db(np.max(np.abs(audio)), silence_db)


def rms_db(audio: np.ndarray, silence_db: float = -np.inf) -> float:
    """RMS level of ``audio`` in dBFS (``silence_db`` for digital silence)."""
    from ..basic import rms

    return amplitude_to_db(rms(audio), silence_db)


def to_db(linear_value: float) -> float:
    """
    Convert linear amplitude value to decibels, flooring the input at 1e-10
    (about -200 dB) so silence maps to a finite value. Use :func:`amplitude_to_db`
    when you need an explicit silence convention.

    Args:
        linear_value: Linear amplitude value

    Returns:
        Value in decibels (dB)
    """
    return float(20 * np.log10(max(linear_value, 1e-10)))
