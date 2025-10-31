# -*- coding: utf-8 -*-

"""
Parallel EQ Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~

Configuration for parallel EQ processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class ParallelEQConfig:
    """Configuration for parallel EQ processing"""
    enable_parallel: bool = True
    max_workers: int = 8
    use_band_grouping: bool = True
    min_bands_for_parallel: int = 8  # Minimum bands to use parallel processing

    # Band grouping strategy
    bass_bands: Tuple[int, int] = (0, 4)      # Bands 0-4: 0-510 Hz
    low_mid_bands: Tuple[int, int] = (4, 8)   # Bands 4-8: 510-1080 Hz
    mid_bands: Tuple[int, int] = (8, 16)      # Bands 8-16: 1080-3150 Hz
    high_mid_bands: Tuple[int, int] = (16, 20) # Bands 16-20: 3150-6400 Hz
    treble_bands: Tuple[int, int] = (20, 26)  # Bands 20-26: 6400-20000 Hz
