"""
Auralis I/O Module
~~~~~~~~~~~~~~~~~

Audio input/output and result handling

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Refactored from Matchering 2.0 by Sergree and contributors
"""

from .loader import load
from .results import Result, pcm16, pcm24
from .saver import save

__all__ = ["load", "save", "Result", "pcm16", "pcm24"]
