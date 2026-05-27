"""
Acceleration Module
~~~~~~~~~~~~~~~~~~~

SIMD accelerator. (#3476 removed the dead ParallelProcessor that lived
here — the actively-used parallel processor is at
`auralis.optimization.parallel_processor`.)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .simd_accelerator import SIMDAccelerator

__all__ = ['SIMDAccelerator']
