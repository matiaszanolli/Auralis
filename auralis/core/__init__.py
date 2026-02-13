"""
Auralis Core Processing
~~~~~~~~~~~~~~~~~~~~~~

Core audio processing and mastering algorithms

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Based on Matchering 2.0 by Sergree and contributors
"""

from .config import UnifiedConfig
from .processor import process

__all__ = ["process", "UnifiedConfig"]
