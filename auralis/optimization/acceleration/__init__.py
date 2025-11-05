# -*- coding: utf-8 -*-

"""
Acceleration Module
~~~~~~~~~~~~~~~~~~~

SIMD and parallel processing accelerators.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .simd_accelerator import SIMDAccelerator
from .parallel_processor import ParallelProcessor

__all__ = ['SIMDAccelerator', 'ParallelProcessor']
