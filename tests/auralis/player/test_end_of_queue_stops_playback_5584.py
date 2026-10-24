"""Regression tests: end of the last track stops playback and notifies (#5584)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`get_audio_chunk()` only acted at end-of-track when an advance was possible.
With no next track (or auto_advance off) and repeat off, nothing stopped
playback or emitted an event: the state machine stayed PLAYING at EOF
forever, returning silence with the position pinned at total_samples
(#5114's clamp), and no consumer polling state/is_playing could learn the
queue had finished.

Real PlaybackController; file manager, queue, integration and processor
stubbed — the behaviour under test is the streaming mixin's state machine.
"""

import threading
from unittest.mock import MagicMock

import numpy as np

from auralis.player.enhanced_audio_player import AudioPlayer
from auralis.player.playback_controller import PlaybackController, PlaybackState


def _make_player(total_samples: int, has_next: bool) -> AudioPlayer:
    player = AudioPlayer.__new__(AudioPlayer)

    player.playback = PlaybackController()

    file_manager = MagicMock()
    file_manager._audio_lock = threading.RLock()
    file_manager.is_loaded.return_value = True
    file_manager.get_total_samples.return_value = total_samples
    # Return real silence slices so the chunk fetch never errors; the chunk
    # content is irrelevant to the state machine under test.
    file_manager.get_audio_chunk.side_effect = (
        lambda pos, size: np.zeros((size, 2), dtype=np.float32)
    )
    player.file_manager = file_manager

    queue = MagicMock()
    queue.has_next_track.return_value = has_next
    player.queue = queue

    integration = MagicMock()
    integration._current_track_dict = {'id': 1, 'title': 'Last'}
    player.integration = integration

    player.processor = MagicMock()
    # get_audio_chunk passes the file's rate as a second arg (#5729).
    player.processor.process_chunk.side_effect = lambda chunk, sample_rate=None: chunk

    player.auto_advance = True
    player._auto_advancing = threading.Event()
    player._advance_generation = 0
    player._advance_thread = None
    player._stop_requested = threading.Event()
    player._pause_requested = threading.Event()
    player._cleanup_in_progress = threading.Event()

    return player


class TestEndOfQueue:
    def test_last_track_stops_playback_and_notifies_once(self):
        """Single-track queue, repeat off: reading past EOF must leave the
        player not-PLAYING and emit exactly one playback_finished."""
        player = _make_player(total_samples=4410, has_next=False)
        player.playback.state = PlaybackState.PLAYING

        finished = []
        player.integration._notify_callbacks = finished.append

        for _ in range(10):
            player.get_audio_chunk(1024)

        assert player.playback.state is not PlaybackState.PLAYING
        assert len(finished) == 1
        assert finished[0]['action'] == 'playback_finished'
        assert finished[0]['track'] == {'id': 1, 'title': 'Last'}

    def test_auto_advance_disabled_stops_at_end_too(self):
        player = _make_player(total_samples=4410, has_next=True)
        player.auto_advance = False
        player.playback.state = PlaybackState.PLAYING

        finished = []
        player.integration._notify_callbacks = finished.append

        for _ in range(10):
            player.get_audio_chunk(1024)

        assert player.playback.state is not PlaybackState.PLAYING
        assert len(finished) == 1

    def test_with_a_next_track_the_player_still_advances(self):
        """Unchanged behaviour: end of track 1 spawns the advance and the
        state machine keeps running (the advance thread swaps the track)."""
        player = _make_player(total_samples=4410, has_next=True)
        player.playback.state = PlaybackState.PLAYING

        advanced = []

        def fake_advance(gen):
            advanced.append(gen)

        player._auto_advance_next = fake_advance

        for _ in range(10):
            player.get_audio_chunk(1024)
        # Join so the thread's is_playing() guard runs before assertions.
        thread = player._advance_thread
        if thread is not None:
            thread.join(timeout=2)

        assert player._advance_thread is not None
        assert advanced, "auto-advance thread did not run"
        assert player.playback.state is PlaybackState.PLAYING
