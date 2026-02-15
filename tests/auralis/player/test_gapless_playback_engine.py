"""
Tests for GaplessPlaybackEngine

Covers:
- Deadlock regression: get_prebuffered_track() must not deadlock (#2197)
- Prebuffer lifecycle: store, retrieve, invalidate
"""

import threading

import numpy as np
import pytest

from auralis.player.gapless_playback_engine import GaplessPlaybackEngine


class TestGetPrebufferedTrackDeadlock:
    """Regression tests for #2197: non-reentrant lock deadlock."""

    def test_get_prebuffered_track_does_not_deadlock(self, gapless_playback_engine):
        """get_prebuffered_track must return without deadlocking when data is prebuffered."""
        engine = gapless_playback_engine

        # Manually prebuffer data (bypass the worker thread)
        audio = np.zeros(44100, dtype=np.float32)
        with engine.update_lock:
            engine.next_track_buffer = audio
            engine.next_track_info = {"file_path": "/tmp/test.wav"}
            engine.next_track_sample_rate = 44100

        # This would deadlock before the fix — use a timeout to detect it
        result = [None]
        exc = [None]

        def call():
            try:
                result[0] = engine.get_prebuffered_track()
            except Exception as e:
                exc[0] = e

        t = threading.Thread(target=call)
        t.start()
        t.join(timeout=2.0)

        assert not t.is_alive(), "get_prebuffered_track() deadlocked"
        assert exc[0] is None, f"Unexpected exception: {exc[0]}"

        audio_out, sr = result[0]
        assert audio_out is not None
        assert sr == 44100
        np.testing.assert_array_equal(audio_out, audio)

    def test_get_prebuffered_track_returns_none_when_empty(self, gapless_playback_engine):
        """get_prebuffered_track returns (None, None) when nothing is prebuffered."""
        audio, sr = gapless_playback_engine.get_prebuffered_track()
        assert audio is None
        assert sr is None

    def test_has_prebuffered_track_remains_usable(self, gapless_playback_engine):
        """has_prebuffered_track still works correctly as a standalone check."""
        engine = gapless_playback_engine
        assert not engine.has_prebuffered_track()

        with engine.update_lock:
            engine.next_track_buffer = np.zeros(100, dtype=np.float32)
            engine.next_track_info = {"file_path": "/tmp/test.wav"}
            engine.next_track_sample_rate = 44100

        assert engine.has_prebuffered_track()

    def test_invalidate_clears_prebuffer(self, gapless_playback_engine):
        """invalidate_prebuffer clears all prebuffered data."""
        engine = gapless_playback_engine

        with engine.update_lock:
            engine.next_track_buffer = np.zeros(100, dtype=np.float32)
            engine.next_track_info = {"file_path": "/tmp/test.wav"}
            engine.next_track_sample_rate = 44100

        engine.invalidate_prebuffer()

        audio, sr = engine.get_prebuffered_track()
        assert audio is None
        assert sr is None
