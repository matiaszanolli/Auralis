# -*- coding: utf-8 -*-

"""
Acceleration Module
~~~~~~~~~~~~~~~~~~~

SIMD and parallel processing accelerators.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .parallel_processor import ParallelProcessor
from .simd_accelerator import SIMDAccelerator

__all__ = ['SIMDAccelerator', 'ParallelProcessor']
