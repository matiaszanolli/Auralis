"""
Acceleration Module
~~~~~~~~~~~~~~~~~~~

SIMD accelerator. (#3476 removed the dead ParallelProcessor that lived here.
The `auralis.optimization.parallel_processor` this note used to redirect to was
itself never reachable from production and was deleted in #4565 — the live
parallel subsystem is `auralis.dsp.eq.parallel_eq_processor`, which is
unrelated despite the similar name.)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .simd_accelerator import SIMDAccelerator

__all__ = ['SIMDAccelerator']
