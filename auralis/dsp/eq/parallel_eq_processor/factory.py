"""
EQ Processor Factory Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Factory functions for creating EQ processor instances

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


from .vectorized_processor import VectorizedEQProcessor


def create_vectorized_eq_processor() -> VectorizedEQProcessor:
    """
    Create vectorized EQ processor instance

    Returns:
        VectorizedEQProcessor instance
    """
    return VectorizedEQProcessor()
