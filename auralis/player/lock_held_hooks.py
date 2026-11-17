"""
Guard for callbacks that run while the player's ``_audio_lock`` is held (#6085).

``AudioFileManager.load_file(on_loaded=...)`` and ``GaplessPlaybackEngine.advance_with_prebuffer(
on_swap=...)`` invoke a caller-supplied hook inside ``_audio_lock``. A hook that reaches a
``PlaybackController`` mutator (seek, play, load_and_stop ...) fires the state callbacks on the
spot, and ``IntegrationManager._on_playback_state_change`` takes ``_position_lock`` then
``_audio_lock`` - the opposite of ``get_playback_info()`` - which is an AB-BA deadlock of every
``_audio_lock`` taker. The contract that prevents it is ``playback.defer_notifications()`` opened
OUTSIDE the lock; this makes breaking it a loud ``LockHeldNotificationError`` on the offending call
instead of a silent total hang of the player.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

_state = threading.local()


class LockHeldNotificationError(RuntimeError):
    """A playback notification fired inside a lock-held hook with no ``defer_notifications()`` scope."""


@contextmanager
def lock_held_hook(name: str) -> Iterator[None]:
    """Mark this thread as running ``name``, a hook invoked while ``_audio_lock`` is held."""
    previous = getattr(_state, "hook", None)
    _state.hook = name
    try:
        yield
    finally:
        _state.hook = previous


def active_lock_held_hook() -> str | None:
    """The lock-held hook this thread is inside, if any."""
    return getattr(_state, "hook", None)
