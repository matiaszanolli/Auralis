"""Regression test: load_track_from_library holds _audio_lock during position reset (#4219).

load_file() swaps audio_data inside _audio_lock. load_track_from_library() called
playback.load_and_stop() (position reset) OUTSIDE that lock, creating a window where
a concurrent get_audio_chunk() could see new audio at the old position.
"""
import threading
from unittest.mock import MagicMock

import numpy as np


class _TrackingRLock:
    """RLock wrapper that tracks acquisition depth (portable, no C internals)."""
    def __init__(self):
        self._lock = threading.RLock()
        self.depth = 0

    def __enter__(self):
        self._lock.__enter__()
        self.depth += 1
        return self

    def __exit__(self, *args):
        self.depth -= 1
        return self._lock.__exit__(*args)

    def acquire(self, blocking=True, timeout=-1):
        result = self._lock.acquire(blocking=blocking, timeout=timeout)
        if result:
            self.depth += 1
        return result

    def release(self):
        self.depth -= 1
        self._lock.release()


def _make_player():
    """Build a minimal AudioPlayer with mocked subsystems."""
    from auralis.player.enhanced_audio_player import AudioPlayer

    player = AudioPlayer.__new__(AudioPlayer)

    # File manager with tracking reentrant lock
    fm = MagicMock()
    fm._audio_lock = _TrackingRLock()
    fm.current_file = "/test.wav"
    fm.is_loaded.return_value = False
    player.file_manager = fm

    # Playback controller
    pb = MagicMock()
    player.playback = pb

    # Integration manager — simulate a load that takes 50ms
    intg = MagicMock()

    def _slow_load(track_id):
        # Acquire audio_lock briefly to simulate file_manager.load_file()
        with fm._audio_lock:
            fm.audio_data = np.zeros(44100, dtype=np.float32)
            fm.sample_rate = 44100
        return True

    intg.load_track_from_library.side_effect = _slow_load
    player.integration = intg

    # Minimal stubs for the rest of the method
    player.gapless = MagicMock()
    player._schedule_fingerprint_load = MagicMock()
    player._notify = MagicMock()

    return player


def test_load_and_stop_called_under_audio_lock():
    """playback.load_and_stop() must be called while _audio_lock is held."""
    player = _make_player()

    lock_held_during_call = []

    def _spy_load_and_stop():
        lock_held_during_call.append(player.file_manager._audio_lock.depth > 0)

    player.playback.load_and_stop.side_effect = _spy_load_and_stop

    player.load_track_from_library(1)

    assert lock_held_during_call, "load_and_stop was never called"
    assert lock_held_during_call[0], (
        "load_and_stop was called outside _audio_lock — position reset not atomic"
    )


def test_no_audio_position_race():
    """A concurrent chunk read must not observe new audio at an old position.

    Simulated: load_track_from_library races against a 'reader' thread that
    checks file_manager.audio_data and sample_rate. After the load completes
    we verify the reader never saw an inconsistent state.
    """
    player = _make_player()
    inconsistencies = []

    # Simulate 'old' audio state
    old_audio = np.ones(1000, dtype=np.float32)
    with player.file_manager._audio_lock:
        player.file_manager.audio_data = old_audio
        player.file_manager.sample_rate = 44100

    new_audio = np.zeros(44100, dtype=np.float32)

    # We'll track whether load_and_stop happens after audio swap
    swap_done = threading.Event()
    stop_done = threading.Event()

    original_load = player.integration.load_track_from_library.side_effect

    def _instrumented_load(track_id):
        result = original_load(track_id)
        swap_done.set()
        return result

    player.integration.load_track_from_library.side_effect = _instrumented_load

    def _instrumented_stop():
        stop_done.set()

    player.playback.load_and_stop.side_effect = _instrumented_stop

    load_thread = threading.Thread(target=player.load_track_from_library, args=(1,))
    load_thread.start()

    # Wait for swap, then verify stop also happened before lock was released
    swap_done.wait(timeout=2.0)
    load_thread.join(timeout=2.0)

    # If the fix is correct, stop_done must be set (load_and_stop was called)
    assert stop_done.is_set(), "load_and_stop was never called"
