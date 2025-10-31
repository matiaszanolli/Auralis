# -*- coding: utf-8 -*-

"""
Auralis Library Scanner (Backward Compatibility Wrapper)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module provides backward compatibility for code that imports
from auralis.library.scanner directly.

The actual implementation has been modularized into:
    auralis/library/scanner/

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

# Re-export everything from the modular implementation
from .scanner import *  # noqa: F401, F403

# Explicitly re-export the main class for clarity
from .scanner import LibraryScanner

__all__ = ['LibraryScanner']
