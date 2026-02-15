"""
Tests for PlaybackController thread safety (#2198)

Covers:
- Concurrent state transitions produce no invalid states
- Position reads are consistent during concurrent seeks
- State transition validation (valid and invalid paths)
"""

import threading

import pytest

from auralis.player.playback_controller import PlaybackController, PlaybackState

VALID_STATES = {s for s in PlaybackState}


class TestPlaybackControllerThreadSafety:
    """Thread safety tests for #2198."""

    def test_concurrent_play_pause_stop_no_invalid_states(self):
        """10 threads calling play/pause/stop simultaneously produce only valid states."""
        controller = PlaybackController()
        observed_states: list[PlaybackState] = []
        lock = threading.Lock()
        iterations = 200
        barrier = threading.Barrier(10)

        def worker(worker_id):
            barrier.wait()
            for i in range(iterations):
                op = (worker_id + i) % 3
                if op == 0:
                    controller.play()
                elif op == 1:
                    controller.pause()
                else:
                    controller.stop()

                state = controller.state
                with lock:
                    observed_states.append(state)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        # Every observed state must be a valid PlaybackState
        for state in observed_states:
            assert state in VALID_STATES, f"Invalid state observed: {state}"

    def test_concurrent_seek_position_consistency(self):
        """Position reads during concurrent seeks return clamped values, never corrupted."""
        controller = PlaybackController()
        controller.play()
        max_samples = 441000  # 10 seconds at 44.1kHz
        observed_positions: list[int] = []
        lock = threading.Lock()
        barrier = threading.Barrier(10)

        def seeker(worker_id):
            barrier.wait()
            for i in range(200):
                target = (worker_id * 1000 + i * 100) % (max_samples + 500)
                controller.seek(target, max_samples)
                pos = controller.position
                with lock:
                    observed_positions.append(pos)

        threads = [threading.Thread(target=seeker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        # All positions must be within [0, max_samples]
        for pos in observed_positions:
            assert 0 <= pos <= max_samples, f"Position out of range: {pos}"


class TestPlaybackControllerStateTransitions:
    """State machine validation."""

    def test_stopped_to_playing(self):
        controller = PlaybackController()
        assert controller.is_stopped()
        assert controller.play()
        assert controller.is_playing()

    def test_playing_to_paused(self):
        controller = PlaybackController()
        controller.play()
        assert controller.pause()
        assert controller.is_paused()

    def test_paused_to_playing(self):
        controller = PlaybackController()
        controller.play()
        controller.pause()
        assert controller.play()
        assert controller.is_playing()

    def test_stop_resets_position(self):
        controller = PlaybackController()
        controller.play()
        controller.seek(10000, 44100)
        assert controller.position == 10000
        controller.stop()
        assert controller.position == 0

    def test_pause_from_stopped_is_noop(self):
        controller = PlaybackController()
        assert not controller.pause()
        assert controller.is_stopped()

    def test_stop_from_stopped_is_noop(self):
        controller = PlaybackController()
        assert not controller.stop()
        assert controller.is_stopped()

    def test_play_from_playing_is_noop(self):
        controller = PlaybackController()
        controller.play()
        assert not controller.play()
        assert controller.is_playing()
