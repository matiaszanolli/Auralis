"""A user skip is not a track completion; only auto-advance records one (#6313).

``next_track()`` called ``integration.record_track_completion()`` unconditionally,
so every REST/user skip bumped ``tracks_played`` and emitted ``track_completed``
exactly like a track that played to its end. ``total_play_time`` had no writer
anywhere and always read 0.0, so it is removed from the session stats.

Real PlaybackController; gapless engine, file manager, queue and integration
stubbed, as in test_auto_advance_unloadable_successor_5706.
"""

import threading
import time
from unittest.mock import MagicMock

import numpy as np

from auralis.player.enhanced_audio_player import AudioPlayer
from auralis.player.integration_manager import IntegrationManager
from auralis.player.playback_controller import PlaybackController, PlaybackState

TOTAL = 4096


def _navigable_player() -> AudioPlayer:
    """Just enough of an AudioPlayer for next_track() to complete an advance."""
    player = AudioPlayer.__new__(AudioPlayer)
    player.playback = PlaybackController()
    player.file_manager = MagicMock()
    player.file_manager.current_file = None
    player.gapless = MagicMock()
    player.gapless.advance_with_prebuffer.return_value = True
    player.integration = MagicMock()
    player._sync_current_track_from_queue = MagicMock()
    player._stop_requested = threading.Event()
    player._pause_requested = threading.Event()
    player._cleanup_in_progress = threading.Event()
    return player


def test_a_user_skip_records_no_completion():
    player = _navigable_player()

    assert player.next_track() is True

    player.integration.record_track_completion.assert_not_called()


def test_a_completed_track_records_exactly_one_completion():
    player = _navigable_player()

    assert player.next_track(completed=True) is True

    player.integration.record_track_completion.assert_called_once_with()


def test_a_failed_advance_records_nothing_even_when_completed():
    player = _navigable_player()
    player.gapless.advance_with_prebuffer.return_value = False

    assert player.next_track(completed=True) is False

    player.integration.record_track_completion.assert_not_called()


def test_auto_advance_at_the_end_of_a_track_marks_it_completed():
    player = AudioPlayer.__new__(AudioPlayer)
    player.playback = PlaybackController()
    fm = MagicMock()
    fm._audio_lock = threading.RLock()
    fm.is_loaded.return_value = True
    fm.get_total_samples.return_value = TOTAL
    fm.get_audio_chunk.side_effect = lambda pos, size: np.zeros((size, 2), dtype=np.float32)
    player.file_manager = fm
    player.queue = MagicMock()
    player.queue.has_next_track.return_value = True
    player.integration = MagicMock()
    player.processor = MagicMock()
    player.processor.process_chunk.side_effect = lambda chunk, sample_rate=None: chunk
    player.auto_advance = True
    player._auto_advancing = threading.Event()
    player._advance_generation = 0
    player._advance_thread = None
    player._stop_requested = threading.Event()
    player._pause_requested = threading.Event()
    player._cleanup_in_progress = threading.Event()
    player.next_track = MagicMock(return_value=True)
    player.playback.position = TOTAL - 1024
    player.playback.state = PlaybackState.PLAYING

    player.get_audio_chunk(1024)  # the final chunk spawns the advance
    deadline = time.monotonic() + 2.0
    while not player.next_track.called and time.monotonic() < deadline:
        time.sleep(0.01)

    player.next_track.assert_called_once_with(completed=True)


def test_session_stats_no_longer_report_a_never_written_play_time():
    manager = IntegrationManager.__new__(IntegrationManager)
    manager._stats_lock = threading.Lock()
    manager._position_lock = threading.RLock()
    manager.tracks_played = 3
    manager.session_start_time = time.time()
    manager._current_track_dict = None
    manager.auto_reference_selection = True
    manager.queue = MagicMock()
    manager.queue.get_queue_info.return_value = {}
    manager.playback = MagicMock()
    manager.playback.get_state_snapshot.return_value = ("stopped", False)
    manager._track_position_snapshot = MagicMock(return_value=(0.0, 0.0, None))
    manager.processor = MagicMock()

    session = manager.get_playback_info()['session']

    assert session['tracks_played'] == 3
    assert 'total_play_time' not in session
