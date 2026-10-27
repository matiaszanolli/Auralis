"""
Regression tests: previous_track() resumes playback (#3712, test debt #3736)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`previous_track()` used a not-stopped state read as its "was the user
playing?" signal. `load_file()` calls `playback.load_and_stop()`, which
unconditionally writes state=STOPPED, so that guard was *always* False by the
time it was evaluated — `play()` was unreachable and every previous-track press
silently halted playback (regression of #2684).

#3712 switched the guard to `_stop_requested.is_set()`: the explicit user-stop
Event (#3296), which `load_file()` never touches, so it distinguishes "the user
pressed stop" from "load_file reset state as part of loading".

These tests use the real PlaybackController — a mocked one would happily report
whatever state the test wanted and would not reproduce the bug — with the file
manager, queue, and library integration stubbed out.
"""

import threading
from unittest.mock import MagicMock

import pytest

from auralis.player.enhanced_audio_player import AudioPlayer
from auralis.player.playback_controller import PlaybackController, PlaybackState

PREV_TRACK = {"file_path": "/music/previous.wav", "title": "Previous"}


def _make_player(load_succeeds: bool = True) -> AudioPlayer:
    """Build an AudioPlayer with a real PlaybackController and stubbed deps."""
    player = AudioPlayer.__new__(AudioPlayer)

    player.playback = PlaybackController()

    file_manager = MagicMock()
    file_manager._audio_lock = threading.RLock()
    # Model the real load_file contract (#5581): the on_loaded hook runs
    # inside the call, so playback.load_and_stop actually executes.
    def _load_file(path, on_loaded=None):
        if on_loaded is not None:
            on_loaded()
        return load_succeeds
    file_manager.load_file.side_effect = _load_file
    file_manager.current_file = PREV_TRACK["file_path"]
    file_manager.get_total_samples.return_value = 44100
    player.file_manager = file_manager

    queue = MagicMock()
    queue.step_previous.return_value = (PREV_TRACK, 3, 2)  # (track, saved, moved_to)
    player.queue = queue

    player.gapless = MagicMock()
    player.integration = MagicMock()
    player._schedule_fingerprint_load = MagicMock()

    # Control flags normally set up in __init__.
    player.auto_advance = True
    player._auto_advancing = threading.Event()
    player._advance_generation = 0
    player._stop_requested = threading.Event()
    player._pause_requested = threading.Event()
    player._advance_thread = None
    player._cleanup_in_progress = threading.Event()

    return player


class TestPreviousTrackResumesPlayback:
    """The user-visible half of #3712."""

    def test_previous_while_playing_resumes(self):
        """previous_track() during playback must leave the player PLAYING."""
        player = _make_player()
        player.playback.state = PlaybackState.PLAYING

        assert player.previous_track() is True

        assert player.is_playing() is True
        assert player.playback.state is PlaybackState.PLAYING

    def test_previous_while_paused_does_not_start_playback(self):
        """A paused player stays paused-or-stopped — previous() never auto-starts."""
        player = _make_player()
        player.playback.state = PlaybackState.PAUSED

        assert player.previous_track() is True

        # was_playing was False, so play() is not called; load_and_stop() ran.
        assert player.is_playing() is False
        assert player.playback.state is PlaybackState.STOPPED

    def test_previous_after_stop_stays_stopped(self):
        """The _stop_requested gate: an explicit stop() suppresses the resume."""
        player = _make_player()
        player.playback.state = PlaybackState.PLAYING

        player.stop()
        assert player._stop_requested.is_set()

        assert player.previous_track() is True

        assert player.is_playing() is False
        assert player.playback.state is PlaybackState.STOPPED

    def test_load_and_stop_ran_before_the_resume_decision(self):
        """Guard against re-introducing a state-read "was playing" guard.

        load_file() drives the controller through STOPPED, so any future
        implementation that reads the playback state as the "was playing" signal
        would see True here and skip the resume. Asserting the STOPPED
        transition really happened keeps that from silently passing.
        """
        player = _make_player()
        observed: list[str] = []
        player.playback.add_callback(lambda info: observed.append(info["action"]))
        player.playback.state = PlaybackState.PLAYING

        player.previous_track()

        assert "stop" in observed, "load_file() must still drive the STOPPED transition"
        assert observed[-1] == "play"
        assert player.is_playing() is True


class TestPreviousTrackFailurePaths:
    """previous_track() must not resume when it has nothing to play."""

    def test_no_previous_track_returns_false_and_does_not_play(self):
        player = _make_player()
        player.queue.step_previous.return_value = (None, 3, 3)
        player.playback.state = PlaybackState.PLAYING

        assert player.previous_track() is False

        # Untouched: no load, no state change.
        player.file_manager.load_file.assert_not_called()
        assert player.playback.state is PlaybackState.PLAYING

    def test_failed_load_rolls_back_index_and_does_not_resume(self):
        """#3442: a failed load restores the queue index instead of resuming.
        #5582: the rollback is a compare-and-set against the index
        step_previous() reports it moved to (saved 3 → moved to 2, #5705)."""
        player = _make_player(load_succeeds=False)
        player.playback.state = PlaybackState.PLAYING

        assert player.previous_track() is False

        player.queue.rollback_index.assert_called_once_with(3, expected_current=2)
        assert player.is_playing() is False


class TestConcurrentStopDuringPrevious:
    """#4126: a stop() landing between the guard and play() must still win."""

    def test_stop_racing_the_resume_leaves_player_stopped(self):
        player = _make_player()
        player.playback.state = PlaybackState.PLAYING

        real_load_file = player.load_file

        def load_then_stop(path: str) -> bool:
            result = real_load_file(path)
            # Simulate the user hitting stop while the load was in flight:
            # _stop_requested is set without holding _audio_lock.
            player._stop_requested.set()
            return result

        player.load_file = load_then_stop  # type: ignore[method-assign]

        assert player.previous_track() is True
        assert player.is_playing() is False


class TestConcurrentPauseDuringPrevious:
    """#5240: a pause() landing between the guard and play() must still win.

    Mirrors TestConcurrentStopDuringPrevious — pause() has no state-read
    state to misread, but it has the identical timing bug: `was_playing` is
    captured before the blocking `load_file()` call, and the resume that
    follows used to be unconditional once `was_playing` was True, silently
    overriding a pause() that raced the load.
    """

    def test_pause_racing_the_resume_leaves_player_paused(self):
        player = _make_player()
        player.playback.state = PlaybackState.PLAYING

        # load_file() calls file_manager.load_file() (the blocking disk read)
        # BEFORE playback.load_and_stop() forces state to STOPPED — so state
        # is still PLAYING for the whole duration of this mocked call. That's
        # the real window a concurrent pause() lands in; patching player.pause()
        # in to *this* mock (rather than after load_file() returns) is what
        # actually reproduces the race instead of pausing a track already
        # forced to STOPPED, where PlaybackController.pause() would no-op.
        def load_file_racing_a_pause(_path: str, on_loaded=None) -> bool:
            # Lands while state is still PLAYING — the real race window.
            player.pause()
            # The swap-section reset, as the real file manager runs it (#5581).
            if on_loaded is not None:
                on_loaded()
            return True

        player.file_manager.load_file.side_effect = load_file_racing_a_pause

        assert player.previous_track() is True
        assert player.is_playing() is False
        assert player.playback.state is PlaybackState.PAUSED

    def test_pause_does_not_leak_across_a_later_explicit_resume(self):
        """`_pause_requested` must clear on the next real play(), not linger."""
        player = _make_player()
        player.playback.state = PlaybackState.PLAYING

        player.pause()
        assert player._pause_requested.is_set()

        player.playback.state = PlaybackState.PAUSED
        assert player.play() is True
        assert player._pause_requested.is_set() is False


class TestNextTrackParity:
    """#3712 applied the same guard to the gapless advance path."""

    def test_advance_uses_stop_requested_not_is_stopped(self):
        """A stopped-by-load controller must still resume on gapless advance."""
        player = _make_player()
        player.playback.state = PlaybackState.PLAYING
        player.gapless.advance_with_prebuffer.return_value = True

        assert player.next_track() is True
        assert player.is_playing() is True

    def test_advance_after_explicit_stop_does_not_resume(self):
        player = _make_player()
        player.playback.state = PlaybackState.PLAYING
        player.gapless.advance_with_prebuffer.return_value = True

        player.stop()
        assert player.next_track() is True
        assert player.is_playing() is False

    def test_advance_after_explicit_pause_does_not_resume(self):
        """#5240: same guard, applied to the gapless next_track() path."""
        player = _make_player()
        player.playback.state = PlaybackState.PLAYING
        player.gapless.advance_with_prebuffer.return_value = True

        player.pause()
        assert player.next_track() is True
        assert player.is_playing() is False
        assert player.playback.state is PlaybackState.PAUSED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
