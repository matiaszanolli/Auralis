"""
Parallel EQ Processing Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

High-performance vectorized processing for psychoacoustic EQ

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .factory import create_vectorized_eq_processor
from .vectorized_processor import VectorizedEQProcessor

__all__ = [
    'VectorizedEQProcessor',
    'create_vectorized_eq_processor',
]
