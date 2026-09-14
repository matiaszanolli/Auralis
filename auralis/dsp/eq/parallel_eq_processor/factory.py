"""
EQ Processor Factory Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Factory functions for creating EQ processor instances

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


from .vectorized_processor import VectorizedEQProcessor


def create_vectorized_eq_processor() -> VectorizedEQProcessor:
    """
    Create vectorized EQ processor instance

    Returns:
        VectorizedEQProcessor instance
    """
    return VectorizedEQProcessor()
