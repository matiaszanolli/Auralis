"""Regression tests: pause() arms _pause_requested before its transition (#5588)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`pause()` used to call `playback.pause()` first and set `_pause_requested`
afterwards — the reverse of stop()'s flag-then-transition order. A concurrent
`play()` between the two lines cleared the flag and the later `set()` re-armed
it while the state was PLAYING, so the next track boundary paused though the
user last pressed play. With set-first, `play()`'s clear after its own
transition wins every interleaving.

The interleave test reproduces the race deterministically: the mocked
transition runs the concurrent play() *inside* pause(), i.e. between the
transition and (the old code's) flag write.

Same harness as test_previous_track_resume.py: a real PlaybackController with
stubbed dependencies — a mocked controller would report whatever state the
test wanted and would not exercise the transitions at all.
"""

import threading
from unittest.mock import MagicMock

from auralis.player.enhanced_audio_player import AudioPlayer
from auralis.player.playback_controller import PlaybackController, PlaybackState


def _make_player() -> AudioPlayer:
    player = AudioPlayer.__new__(AudioPlayer)

    player.playback = PlaybackController()

    file_manager = MagicMock()
    file_manager._audio_lock = threading.RLock()
    file_manager.is_loaded.return_value = True
    player.file_manager = file_manager

    player.queue = MagicMock()
    player.gapless = MagicMock()
    player.integration = MagicMock()

    player.auto_advance = True
    player._auto_advancing = threading.Event()
    player._advance_generation = 0
    player._stop_requested = threading.Event()
    player._pause_requested = threading.Event()
    player._advance_thread = None
    player._cleanup_in_progress = threading.Event()

    return player


class TestPauseFlagOrdering:
    def test_successful_pause_sets_the_flag(self):
        player = _make_player()
        player.playback.state = PlaybackState.PLAYING

        assert player.pause() is True

        assert player.playback.state is PlaybackState.PAUSED
        assert player._pause_requested.is_set()

    def test_failed_pause_leaves_the_flag_unset(self):
        """A pause() on a non-playing player must not arm a stale flag."""
        player = _make_player()
        player.playback.state = PlaybackState.STOPPED

        assert player.pause() is False

        assert player.playback.state is PlaybackState.STOPPED
        assert not player._pause_requested.is_set()

    def test_play_interleaved_inside_pause_ends_with_the_flag_cleared(self):
        """The #5588 interleave, made deterministic: T2's play() runs between
        T1's transition and the flag write. The final state PLAYING must carry
        a cleared flag — the old set-after-transition order left it armed."""
        player = _make_player()
        player.playback.state = PlaybackState.PLAYING

        original_pause = player.playback.pause

        def interleaved_pause() -> bool:
            paused = original_pause()
            # T2 presses play while T1's pause() is still in flight.
            player.play()
            return paused

        player.playback.pause = interleaved_pause

        assert player.pause() is True

        assert player.playback.state is PlaybackState.PLAYING
        assert not player._pause_requested.is_set()
