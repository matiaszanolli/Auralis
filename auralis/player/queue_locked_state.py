"""
QueueController's locked mirrors of QueueManager's scalar state (split from
queue_controller.py, #5836).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .components import QueueManager


class QueueLockedStateMixin:
    """``current_index`` / ``shuffle_enabled`` / ``repeat_enabled`` read and written under the queue lock."""

    queue: QueueManager

    # #3783: route every read/write of QueueManager attributes through the
    # _lock that QueueManager itself uses for its mutators. CPython's GIL
    # kept simple-attribute reads torn-free historically, but free-threaded
    # builds (PEP 703) need explicit synchronization here, and the previous
    # raw `self.queue.current_index` accesses violated the QueueManager
    # invariant that the lock protects the full state transition.

    @property
    def current_index(self) -> int:
        """Get current track index (#3783: locked via QueueManager._lock)."""
        with self.queue._lock:
            return self.queue.current_index

    @current_index.setter
    def current_index(self, value: int) -> None:
        """Set current track index (#3783: locked)."""
        with self.queue._lock:
            self.queue.current_index = value

    @property
    def shuffle_enabled(self) -> bool:
        """Get shuffle mode status (#3783: locked)."""
        with self.queue._lock:
            return self.queue.shuffle_enabled

    @shuffle_enabled.setter
    def shuffle_enabled(self, value: bool) -> None:
        """Set shuffle mode (#3783: locked)."""
        with self.queue._lock:
            self.queue.shuffle_enabled = value

    @property
    def repeat_enabled(self) -> bool:
        """Get repeat mode status (#3783: locked)."""
        with self.queue._lock:
            return self.queue.repeat_enabled

    @repeat_enabled.setter
    def repeat_enabled(self, value: bool) -> None:
        """Set repeat mode (#3783: locked)."""
        with self.queue._lock:
            self.queue.repeat_enabled = value
