"""
Parallel EQ Processing Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

High-performance parallel processing for psychoacoustic EQ

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .config import ParallelEQConfig
from .factory import (
    create_optimal_eq_processor,
    create_parallel_eq_processor,
    create_vectorized_eq_processor,
)
from .parallel_processor import ParallelEQProcessor
from .vectorized_processor import VectorizedEQProcessor

__all__ = [
    'ParallelEQConfig',
    'ParallelEQProcessor',
    'VectorizedEQProcessor',
    'create_parallel_eq_processor',
    'create_vectorized_eq_processor',
    'create_optimal_eq_processor',
]
