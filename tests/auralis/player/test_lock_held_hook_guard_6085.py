"""
A notification fired inside a lock-held hook raises instead of deadlocking (#6085)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``load_file(on_loaded=...)`` and ``advance_with_prebuffer(on_swap=...)`` run a caller hook inside
``_audio_lock``. A hook that seeks/plays/stops without the caller's ``defer_notifications()`` scope
would dispatch the state callbacks under the lock - the AB-BA deadlock with ``get_playback_info()``.
It now fails the call loudly; the documented usage (defer scope OUTSIDE the lock) is untouched.
"""

import threading
from unittest.mock import patch

import numpy as np
import pytest

from auralis.player.audio_file_manager import AudioFileManager
from auralis.player.lock_held_hooks import (
    LockHeldNotificationError,
    active_lock_held_hook,
    lock_held_hook,
)
from auralis.player.playback_controller import PlaybackController, PlaybackState


@pytest.fixture
def loaded_audio(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")  # exists(); decode is patched
    with patch(
        "auralis.player.audio_file_manager.load",
        return_value=(np.zeros((100, 2), dtype=np.float32), 44100),
    ):
        yield str(wav)


def _controller_with_callback():
    playback = PlaybackController()
    seen: list[dict | None] = []
    playback.add_callback(seen.append)
    return playback, seen


def test_a_notification_inside_the_hook_without_a_defer_scope_raises(loaded_audio):
    manager = AudioFileManager()
    playback, seen = _controller_with_callback()

    # load_file reports failure rather than raising, so capture what the hook saw
    outcomes: list[BaseException] = []

    def on_loaded():
        try:
            playback.seek(0, 100)
        except LockHeldNotificationError as exc:
            outcomes.append(exc)

    manager.load_file(loaded_audio, on_loaded=on_loaded)

    assert len(outcomes) == 1 and "on_loaded" in str(outcomes[0])
    assert seen == [], "no callback may have been dispatched under the lock"


def test_with_the_defer_scope_outside_the_lock_the_hook_works_and_notifies_afterwards(loaded_audio):
    manager = AudioFileManager()
    playback, seen = _controller_with_callback()
    notified_while_locked: list[bool] = []
    playback.add_callback(lambda info: notified_while_locked.append(manager._audio_lock._is_owned()))

    with playback.defer_notifications():
        assert manager.load_file(loaded_audio, on_loaded=lambda: playback.seek(0, 100)) is True

    assert [info["action"] for info in seen if info] == ["seek"]
    assert notified_while_locked == [False], "the flush happens once _audio_lock is released"


def test_the_marker_is_scoped_to_the_hook_and_to_its_thread():
    assert active_lock_held_hook() is None
    with lock_held_hook("on_swap"):
        assert active_lock_held_hook() == "on_swap"
        other_thread: list[str | None] = []
        thread = threading.Thread(target=lambda: other_thread.append(active_lock_held_hook()))
        thread.start()
        thread.join()
        assert other_thread == [None]
    assert active_lock_held_hook() is None


def test_the_marker_is_cleared_even_when_the_hook_raises():
    with pytest.raises(ValueError):
        with lock_held_hook("on_swap"):
            raise ValueError("boom")
    assert active_lock_held_hook() is None


def test_a_mutator_outside_any_hook_notifies_immediately_as_before():
    playback, seen = _controller_with_callback()
    playback.state = PlaybackState.PAUSED

    playback.play()

    assert [info["action"] for info in seen if info] == ["play"]
