"""
DB Conversion Utilities
~~~~~~~~~~~~~~~~~~~~~~~

Unified dB conversion utilities to eliminate duplicate 20*log10 patterns.
Replaces 17+ instances of the same calculation across processing modes.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np


class DBConversion:
    """
    Unified dB conversion utilities to eliminate duplicate 20*log10 patterns.
    Replaces 17+ instances of the same calculation across processing modes.
    """

    @staticmethod
    def to_db(value: float, default: float = -np.inf) -> float:
        """
        Convert linear amplitude to dB with safe handling of zero/negative values.

        Args:
            value: Linear amplitude value (typically 0-1 for audio)
            default: Value to return if input is <= 0 (default: -np.inf)

        Returns:
            Amplitude in dB (20 * log10(value)) or default if value <= 0
        """
        return 20 * np.log10(value) if value > 0 else default

    @staticmethod
    def to_linear(db: float) -> float:
        """
        Convert dB to linear amplitude.

        Args:
            db: Value in dB

        Returns:
            Linear amplitude (10^(db/20))
        """
        return 10 ** (db / 20)

    @staticmethod
    def db_delta(before_db: float, after_db: float) -> float:
        """
        Calculate change in dB with safe handling of -inf values.

        Args:
            before_db: Before value in dB
            after_db: After value in dB

        Returns:
            Change in dB (after - before), handling -inf gracefully
        """
        if np.isinf(before_db) or np.isinf(after_db):
            return 0.0 if np.isinf(before_db) and np.isinf(after_db) else np.inf
        return after_db - before_db
