"""
Player Components
~~~~~~~~~~~~~~~~~

Modular components for audio player

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .queue_manager import QueueManager, create_queue_manager

__all__ = [
    'QueueManager',
    'create_queue_manager',
]
