"""
Parallel EQ Processing
~~~~~~~~~~~~~~~~~~~~~~

High-performance parallel processing for psychoacoustic EQ

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

BACKWARD COMPATIBILITY WRAPPER
This file re-exports from the modular parallel_eq_processor package.
"""

# Re-export all public classes and functions for backward compatibility
from .parallel_eq_processor import (
    ParallelEQConfig,
    ParallelEQProcessor,
    VectorizedEQProcessor,
    create_optimal_eq_processor,
    create_parallel_eq_processor,
    create_vectorized_eq_processor,
)

__all__ = [
    'ParallelEQConfig',
    'ParallelEQProcessor',
    'VectorizedEQProcessor',
    'create_parallel_eq_processor',
    'create_vectorized_eq_processor',
    'create_optimal_eq_processor',
]
