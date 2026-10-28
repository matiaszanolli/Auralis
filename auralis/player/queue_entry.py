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
