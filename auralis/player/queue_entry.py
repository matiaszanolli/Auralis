"""
Queue entry file path (#5563)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Production queue entries are built by ``QueueController.set_queue`` as
``{'filepath': ...}``, but the engine's next / previous / gapless / prebuffer code read only
``file_path`` and ``path``. On a production queue ``peek_next_track().get('file_path')`` was
``None``, so a gapless advance returned False ("no file path") and never prebuffered; library
dicts (``Track.to_dict()``) use ``filepath`` as well. One reader for every key spelling.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Mapping
from typing import Any


def entry_path(entry: Mapping[str, Any] | None) -> str | None:
    """The file path of a queue entry, whichever key it carries; None if it has none."""
    if not entry:
        return None
    return entry.get('filepath') or entry.get('file_path') or entry.get('path') or None


class QueueEntryTrack:
    """Stand-in for a library Track when all that is known is the queue entry (#5726).

    ``IntegrationManager.set_current_track`` only ran from ``load_track_from_library``, so after a
    queue-driven advance (next / previous / auto-advance) ``current_track`` and the dict behind
    every playback-state payload and the ``playback_finished`` event kept describing whichever
    track was loaded last. Its ``to_dict()`` is the entry minus the filesystem path (#3205).
    """

    _PATH_KEYS = frozenset({'filepath', 'file_path', 'path'})

    def __init__(self, entry: Mapping[str, Any]) -> None:
        self._entry = dict(entry)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self._entry.items() if k not in self._PATH_KEYS}
