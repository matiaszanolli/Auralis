"""
One engine-level lock for every operation that changes the loaded track (#6531, the engine half of #6082).

The loaded track is several pieces written in separate critical sections: the audio buffer and
``current_file`` (swapped under ``_audio_lock``), ``current_track`` (under ``_position_lock``), the
queue pointer and the scheduled fingerprint. Two loads that overlapped (a double click, a load
racing ``next_track``) settled in decode-completion order, so the audio of one track could end up
with the ``current_track`` of the other, and two concurrent first ``add_to_queue`` calls selected
only one of them. Each track-changing method of ``AudioPlayer`` now runs holding the player's
``_track_change_lock``, an RLock taken outermost (before ``_audio_lock`` and every other player
lock), so one change completes before the next starts and nested calls (``previous_track`` ->
``load_track_from_library``) re-enter it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import functools
import threading
from collections.abc import Callable
from typing import Any, TypeVar, cast

_Method = TypeVar("_Method", bound=Callable[..., Any])


def _track_change_lock(player: Any) -> threading.RLock:
    """The player's lock; created on first use (dict.setdefault is atomic) for a player built bare."""
    state: dict[str, Any] = vars(player)
    lock: threading.RLock | None = state.get("_track_change_lock")
    if lock is None:
        lock = cast(threading.RLock, state.setdefault("_track_change_lock", threading.RLock()))
    return lock


def serialised_track_change(method: _Method) -> _Method:
    """Run ``method`` holding its player's ``_track_change_lock``; never call it under ``_audio_lock``."""

    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        with _track_change_lock(self):
            return method(self, *args, **kwargs)

    return cast(_Method, wrapper)
