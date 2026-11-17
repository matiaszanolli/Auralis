"""
The audio mtime as a sidecar records and compares it (#6325).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from datetime import datetime, timezone
from typing import Any


def modified_at_stamp(mtime: float) -> str:
    """The file mtime as an offset-aware UTC string, the same on every machine.

    Sidecars travel with the audio (NAS, external drive, another host), and the old naive local-time
    string changed with ``TZ`` for the same instant, invalidating a perfectly good sidecar.
    """
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()


def mtime_matches(recorded: Any, mtime: float) -> bool:
    """Whether a sidecar's recorded ``modified_at`` describes *mtime*.

    A sidecar written before #6325 holds a naive local-time string: still honoured on the machine
    whose timezone wrote it, replaced by a UTC stamp the next time it is rewritten.
    """
    return recorded in (modified_at_stamp(mtime), datetime.fromtimestamp(mtime).isoformat())
