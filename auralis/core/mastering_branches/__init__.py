"""
Mastering Processing Branches
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Strategy pattern implementation for material-specific mastering processing.

Breaks apart the monolithic _process() method into focused, testable branches
based on material classification (compressed loud, dynamic loud, quiet).

This package was split out of the former single ``mastering_branches.py`` module
(#4252); the barrel below preserves the original public import surface so call
sites (``from auralis.core.mastering_branches import MaterialClassifier`` etc.)
continue to work unchanged.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .base import ProcessingBranch
from .classifier import MaterialClassifier
from .compressed_loud import CompressedLoudBranch
from .dynamic_loud import DynamicLoudBranch
from .quiet import QuietBranch

__all__ = [
    "MaterialClassifier",
    "ProcessingBranch",
    "CompressedLoudBranch",
    "DynamicLoudBranch",
    "QuietBranch",
]
