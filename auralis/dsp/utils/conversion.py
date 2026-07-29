"""
Audio Conversion Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~

Conversion functions between different audio representations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np


def to_db(linear_value: float) -> float:
    """
    Convert linear amplitude value to decibels

    Args:
        linear_value: Linear amplitude value

    Returns:
        Value in decibels (dB)
    """
    return float(20 * np.log10(max(linear_value, 1e-10)))
