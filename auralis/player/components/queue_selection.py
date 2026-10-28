"""
Queue selection (#5727)
~~~~~~~~~~~~~~~~~~~~~~~

add_to_queue() appends a track and loads it when nothing is loaded, but ``add_track`` leaves
``current_index == -1`` on an empty queue. The loaded track was therefore not "current":
``get_current_track()`` was None and ``peek_next()`` returned the same track again, so it played twice.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from typing import Any


class QueueSelectionMixin:
    """Selection helpers; ``tracks``, ``current_index`` and ``_lock`` belong to QueueManager."""

    tracks: list[dict[str, Any]]
    current_index: int
    _lock: "threading.RLock"

    def select_if_unselected(self, track_info: dict[str, Any]) -> bool:
        """Select ``track_info`` (the last entry) if nothing is selected; True if it did."""
        with self._lock:
            if self.current_index >= 0 or not self.tracks or self.tracks[-1] is not track_info:
                return False
            self.current_index = len(self.tracks) - 1
            return True
