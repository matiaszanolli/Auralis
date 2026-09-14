"""
Processing Mode Modules
~~~~~~~~~~~~~~~~~~~~~~~

Mode-specific processing logic

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .reference_mode import apply_reference_matching

__all__ = [
    'apply_reference_matching',
]
