"""
Regression: an unloadable successor ends playback once, not in a retry storm (#5706)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``_auto_advance_next`` ignored a False return from ``next_track()`` (successor
missing, corrupt, or without a path key). Its ``finally`` re-armed the spawn, so
every later ``get_audio_chunk()`` at the track end started another advance
thread -- thousands of attempts a second, with playback never finishing.

Real PlaybackController; file manager, queue, integration and processor stubbed,
as in test_end_of_queue_stops_playback_5584.
"""

import threading
import time
from unittest.mock import MagicMock

import numpy as np

from auralis.player.enhanced_audio_player import AudioPlayer
from auralis.player.playback_controller import PlaybackController, PlaybackState

TOTAL = 4096


def _make_player(next_track_result: bool = False) -> AudioPlayer:
    player = AudioPlayer.__new__(AudioPlayer)
    player.playback = PlaybackController()

    file_manager = MagicMock()
    file_manager._audio_lock = threading.RLock()
    file_manager.is_loaded.return_value = True
    file_manager.get_total_samples.return_value = TOTAL
    file_manager.get_audio_chunk.side_effect = lambda pos, size: np.zeros((size, 2), dtype=np.float32)
    player.file_manager = file_manager

    queue = MagicMock()
    queue.has_next_track.return_value = True  # a successor exists in the queue...
    player.queue = queue

    integration = MagicMock()
    integration._current_track_dict = {'id': 1, 'title': 'First'}
    player.integration = integration

    player.processor = MagicMock()
    player.processor.process_chunk.side_effect = lambda chunk, sample_rate=None: chunk

    player.auto_advance = True
    player._auto_advancing = threading.Event()
    player._advance_generation = 0
    player._advance_thread = None
    player._stop_requested = threading.Event()
    player._pause_requested = threading.Event()
    player._cleanup_in_progress = threading.Event()

    # ...but loading it fails.
    player.next_track = MagicMock(return_value=next_track_result)
    player.playback.position = TOTAL - 1024
    player.playback.state = PlaybackState.PLAYING
    return player


def _drive(player: AudioPlayer, seconds: float = 0.5) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        player.get_audio_chunk(1024)


def _finished_events(player: AudioPlayer) -> list:
    return [c for c in player.integration._notify_callbacks.call_args_list
            if c.args[0].get('action') == 'playback_finished']


def test_an_unloadable_successor_is_attempted_once():
    player = _make_player(next_track_result=False)

    _drive(player)

    assert player.next_track.call_count == 1


def test_playback_ends_stopped_with_exactly_one_notification():
    player = _make_player(next_track_result=False)

    _drive(player)

    assert player.playback.state is PlaybackState.STOPPED
    assert len(_finished_events(player)) == 1


def test_a_successful_advance_does_not_finish_playback():
    player = _make_player(next_track_result=True)

    _drive(player, seconds=0.2)

    assert _finished_events(player) == []
    assert player.playback.state is PlaybackState.PLAYING


def test_a_user_stop_during_the_advance_is_not_announced_as_a_finish():
    player = _make_player(next_track_result=False)
    player.next_track.side_effect = lambda: (player._stop_requested.set(), False)[1]

    _drive(player, seconds=0.2)

    assert _finished_events(player) == []


def test_an_exception_from_next_track_still_stops_playback():
    player = _make_player()
    player.next_track.side_effect = RuntimeError("queue race")

    _drive(player, seconds=0.2)

    assert player.playback.state is PlaybackState.STOPPED
    assert player.next_track.call_count == 1
