"""
Band Normalization Table
~~~~~~~~~~~~~~~~~~~~~~~~~

Parametric band normalization for EQ parameter mapping.

Replaces repetitive loops in parameter_mapper.py with data-driven approach.
Each band definition specifies:
- Band index range (start, end)
- Energy dimension name
- Min and max dB values

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any
from collections.abc import Callable

import numpy as np


class BandNormalizationTable:
    """
    Parametric band normalization for EQ parameter mapping.

    Replaces repetitive loops in parameter_mapper.py with data-driven approach.
    Each band definition specifies:
    - Band index range (start, end)
    - Energy dimension name
    - Min and max dB values
    """

    # Standard 31-band EQ configuration with frequency ranges and gain ranges
    # Total bands: 0-30 (31 bands inclusive)
    STANDARD_BANDS = [
        # (band_start, band_end, freq_range_hz, fingerprint_key, min_db, max_db)
        (0, 3, "20-60", "sub_bass_pct", -12, 12),
        (4, 11, "60-250", "bass_pct", -12, 12),
        (12, 14, "250-500", "low_mid_pct", -6, 6),
        (15, 19, "500-2k", "mid_pct", -6, 6),
        (20, 23, "2k-4k", "upper_mid_pct", -8, 8),
        (24, 25, "4k-6k", "presence_pct", -6, 12),
        (26, 30, "6k-20k", "air_pct", -12, 12),
    ]

    def __init__(self, band_definitions: list[tuple[int, int, str, str, int, int]] | None = None) -> None:
        """
        Initialize band normalization table.

        Args:
            band_definitions: List of band tuples or None for standard
        """
        self.bands: list[tuple[int, int, str, str, int, int]] = band_definitions if band_definitions is not None else self.STANDARD_BANDS

    def apply_to_fingerprint(self, fingerprint: dict[str, Any], normalize_func: Callable[[float, float, float], float]) -> dict[int, float]:
        """
        Apply band normalization to fingerprint using vectorized operations.

        Args:
            fingerprint: Fingerprint dict with energy percentages
            normalize_func: Function(value, min_db, max_db) → gain_db

        Returns:
            Dictionary mapping band index to gain in dB
        """
        eq_gains: dict[int, float] = {}

        for band_start, band_end, freq_range, fp_key, min_db, max_db in self.bands:
            energy_value: float = float(fingerprint.get(fp_key, 0.1))

            # Calculate gain using provided normalization function
            gain: float = normalize_func(energy_value, min_db, max_db)

            # Apply to all bands in range (vectorized via direct assignment)
            for i in range(band_start, band_end + 1):
                eq_gains[i] = gain

        return eq_gains

    @staticmethod
    def normalize_to_db(value: float, min_db: float, max_db: float) -> float:
        """
        Normalize a 0-1 value to dB range.

        Args:
            value: Input value [0, 1]
            min_db: Minimum dB
            max_db: Maximum dB

        Returns:
            Gain in dB
        """
        value_clipped: float | np.ndarray = np.clip(value, 0.0, 1.0)
        result: float = float(min_db + (value_clipped * (max_db - min_db)))
        return result
