# -*- coding: utf-8 -*-

"""
Player Components
~~~~~~~~~~~~~~~~~

Modular components for audio player

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .queue_manager import QueueManager, create_queue_manager

__all__ = [
    'QueueManager',
    'create_queue_manager',
]
