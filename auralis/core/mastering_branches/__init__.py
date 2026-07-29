"""
Mastering Processing Branches
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shared base and the single continuous mastering path.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .base import ProcessingBranch
from .continuous import ContinuousMasteringBranch

__all__ = [
    "ContinuousMasteringBranch",
    "ProcessingBranch",
]
