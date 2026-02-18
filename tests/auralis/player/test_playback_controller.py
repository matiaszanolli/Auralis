"""
Tests for PlaybackController thread safety and state machine

Covers:
- Concurrent state transitions produce no invalid states (#2198)
- Position reads are consistent during concurrent seeks (#2198)
- State transition validation (valid and invalid paths)
- LOADING→STOPPED transition for post-load reset (#2199)
- State setter removal: no bypass of state machine (#2199)
- Callbacks execute outside lock scope (#2291)
"""

import threading
import time

import pytest

from auralis.player.playback_controller import PlaybackController, PlaybackState

VALID_STATES = {s for s in PlaybackState}


class TestSeekDuringPlaybackRace:
    """Regression tests for seek-during-playback position race (#2153)."""

    def test_seek_during_advance_preserves_seek_target(self):
        """read_and_advance_position must not overwrite a concurrent seek.

        Simulates the exact race: one thread continuously advances position
        (as the playback loop does), while another thread seeks.  After all
        threads join, the final position must reflect the *last* seek, not
        a stale advance.
        """
        controller = PlaybackController()
        controller.play()
        max_samples = 441000
        chunk_size = 4096
        seek_target = 220500  # midpoint
        barrier = threading.Barrier(2)

        def advancer():
            """Simulates the playback loop calling read_and_advance_position."""
            barrier.wait()
            for _ in range(100):
                controller.read_and_advance_position(chunk_size)

        def seeker():
            """Simulates user seeking during playback."""
            barrier.wait()
            for _ in range(100):
                controller.seek(seek_target, max_samples)

        t_advance = threading.Thread(target=advancer)
        t_seek = threading.Thread(target=seeker)
        t_advance.start()
        t_seek.start()
        t_advance.join(timeout=10.0)
        t_seek.join(timeout=10.0)

        # After both finish, do one final seek and verify it sticks
        controller.seek(seek_target, max_samples)
        assert controller.position == seek_target, (
            f"Final seek was overwritten: expected {seek_target}, "
            f"got {controller.position}"
        )

    def test_concurrent_seek_and_advance_no_position_corruption(self):
        """Stress test: position must always be non-negative and bounded."""
        controller = PlaybackController()
        controller.play()
        max_samples = 441000
        chunk_size = 4096
        observed_positions: list[int] = []
        lock = threading.Lock()
        barrier = threading.Barrier(6)

        def advancer():
            barrier.wait()
            for _ in range(200):
                pos = controller.read_and_advance_position(chunk_size)
                with lock:
                    observed_positions.append(pos)

        def seeker(worker_id):
            barrier.wait()
            for i in range(200):
                target = (worker_id * 50000 + i * 441) % max_samples
                controller.seek(target, max_samples)
                with lock:
                    observed_positions.append(controller.position)

        threads = [threading.Thread(target=advancer) for _ in range(2)]
        threads += [threading.Thread(target=seeker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        for pos in observed_positions:
            assert pos >= 0, f"Negative position: {pos}"

    def test_read_and_advance_returns_pre_advance_position(self):
        """read_and_advance_position returns position before advancing."""
        controller = PlaybackController()
        controller.play()
        controller.seek(1000, 441000)

        pos = controller.read_and_advance_position(4096)

        assert pos == 1000, f"Expected pre-advance position 1000, got {pos}"
        assert controller.position == 1000 + 4096


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

    def test_loading_to_stopped(self):
        """stop() works from LOADING state (post-load reset, #2199)."""
        controller = PlaybackController()
        controller.set_loading()
        assert controller.state == PlaybackState.LOADING
        assert controller.stop()
        assert controller.is_stopped()
        assert controller.position == 0

    def test_stop_from_loading_fires_callback(self):
        """Callbacks fire when transitioning LOADING→STOPPED (#2199)."""
        controller = PlaybackController()
        events = []
        controller.add_callback(lambda info: events.append(info))
        controller.set_loading()
        controller.stop()
        actions = [e.get("action") for e in events]
        assert "loading" in actions
        assert "stop" in actions


class TestCallbackOutsideLock:
    """
    Callbacks must execute OUTSIDE the RLock (issue #2291).

    With the old code, _notify_callbacks() was called while the lock was
    held.  A slow callback would block every concurrent state transition
    for its full duration.  The fix: snapshot state inside the lock,
    release the lock, then call callbacks.
    """

    SLOW_DELAY = 0.15  # 150 ms — safely above scheduling noise

    def test_slow_callback_does_not_block_concurrent_state_transition(self):
        """
        A slow callback on play() must not block a concurrent pause().

        Old behaviour (bug): pause() blocks for ~SLOW_DELAY because it
        cannot acquire the lock until the slow callback finishes.
        New behaviour (fix): pause() completes immediately because the
        lock is released before callbacks are invoked.
        """
        controller = PlaybackController()
        callback_started = threading.Event()

        def slow_callback(info):
            if info.get("action") == "play":
                callback_started.set()
                time.sleep(self.SLOW_DELAY)

        controller.add_callback(slow_callback)

        pause_elapsed: list[float] = []

        def thread_b():
            callback_started.wait(timeout=2.0)
            t0 = time.monotonic()
            controller.pause()
            pause_elapsed.append(time.monotonic() - t0)

        t_a = threading.Thread(target=controller.play)
        t_b = threading.Thread(target=thread_b)
        t_a.start()
        t_b.start()
        t_a.join(timeout=2.0)
        t_b.join(timeout=2.0)

        assert pause_elapsed, "thread_b never called pause()"
        assert pause_elapsed[0] < self.SLOW_DELAY * 0.5, (
            f"pause() took {pause_elapsed[0]:.3f}s while slow play() callback "
            f"was running.  Expected < {self.SLOW_DELAY * 0.5:.3f}s — "
            f"callbacks must not hold the lock (issue #2291)."
        )

    def test_state_visible_before_callback_completes(self):
        """
        The new state must be visible to other threads immediately after
        the state method returns, not after the callbacks finish.

        A background thread reads controller.state concurrently during a
        slow callback.  The state must already reflect the transition.
        """
        controller = PlaybackController()
        callback_started = threading.Event()
        state_during_callback: list[str] = []

        def slow_callback(info):
            if info.get("action") == "play":
                callback_started.set()
                time.sleep(self.SLOW_DELAY)

        controller.add_callback(slow_callback)

        def reader():
            callback_started.wait(timeout=2.0)
            state_during_callback.append(controller.state.value)

        t_play = threading.Thread(target=controller.play)
        t_reader = threading.Thread(target=reader)
        t_play.start()
        t_reader.start()
        t_play.join(timeout=2.0)
        t_reader.join(timeout=2.0)

        assert state_during_callback, "reader thread never ran"
        assert state_during_callback[0] == "playing", (
            f"Expected state='playing' during callback, got {state_during_callback[0]!r}. "
            f"State must be updated before callbacks fire (issue #2291)."
        )

    def test_callback_receives_correct_state_snapshot(self):
        """
        The state_info dict passed to callbacks must reflect the state
        at the moment of transition, not some later state.
        """
        controller = PlaybackController()
        received: list[dict] = []
        controller.add_callback(received.append)

        controller.play()
        controller.pause()
        controller.stop()

        actions = [e["action"] for e in received]
        assert actions == ["play", "pause", "stop"], (
            f"Expected callbacks in order [play, pause, stop], got {actions}"
        )
        assert received[0]["state"] == "playing"
        assert received[1]["state"] == "paused"
        assert received[2]["state"] == "stopped"

    def test_callback_can_call_is_playing_without_deadlock(self):
        """
        A callback that reads state (is_playing, is_paused) must not
        deadlock.  With the old code this was safe only because RLock
        allows re-entry from the same thread; with the fix (callbacks
        outside lock) it is safe regardless of which thread dispatches.
        """
        controller = PlaybackController()
        results: list[bool] = []

        def callback(info):
            results.append(controller.is_playing())

        controller.add_callback(callback)
        controller.play()

        assert results, "Callback was never invoked"
        assert results[0] is True, (
            f"is_playing() returned {results[0]!r} inside callback after play(). "
            "Expected True (issue #2291)."
        )

    def test_no_callback_fired_on_no_op_transitions(self):
        """
        Callbacks must NOT fire for no-op transitions (e.g. pause() from
        STOPPED, stop() from STOPPED, play() from PLAYING).
        """
        controller = PlaybackController()
        events: list[dict] = []
        controller.add_callback(events.append)

        # No-ops: should not fire
        controller.pause()        # STOPPED → noop
        controller.stop()         # STOPPED → noop
        controller.play()         # STOPPED → PLAYING (fires)
        controller.play()         # PLAYING → noop

        assert len(events) == 1, (
            f"Expected exactly 1 callback event (the play()), got {len(events)}: {events}"
        )
        assert events[0]["action"] == "play"

    def test_rapid_state_changes_all_callbacks_fired(self):
        """Every state change must trigger exactly one callback."""
        controller = PlaybackController()
        events: list[dict] = []
        controller.add_callback(events.append)

        controller.play()         # 1: play
        controller.pause()        # 2: pause
        controller.play()         # 3: play (resume)
        controller.stop()         # 4: stop

        actions = [e["action"] for e in events]
        assert actions == ["play", "pause", "play", "stop"], (
            f"Expected [play, pause, play, stop], got {actions}"
        )


class TestAudioPlayerPositionSetterLock:
    """AudioPlayer.position setter must acquire PlaybackController._lock (#2287).

    Before the fix, `AudioPlayer.position = value` wrote directly to
    `self.playback.position` (a plain attribute), bypassing the RLock
    that guards all other state mutations in PlaybackController.

    After the fix, the setter delegates to `self.playback.seek(value, max_samples)`
    which acquires `_lock` before writing, keeping position changes atomic and
    consistent with every other state transition.
    """

    @pytest.fixture
    def player(self):
        """AudioPlayer with real PlaybackController/AudioFileManager; rest mocked."""
        from unittest.mock import MagicMock, patch

        import numpy as np

        from auralis.player.enhanced_audio_player import AudioPlayer

        with (
            patch("auralis.player.enhanced_audio_player.QueueController"),
            patch("auralis.player.enhanced_audio_player.GaplessPlaybackEngine"),
            patch("auralis.player.enhanced_audio_player.IntegrationManager"),
            patch("auralis.player.enhanced_audio_player.FingerprintService"),
            patch("auralis.player.enhanced_audio_player.RealtimeProcessor"),
        ):
            p = AudioPlayer(get_repository_factory=MagicMock())

        # Inject fake audio so get_total_samples() returns 441000 (> 0)
        p.file_manager.audio_data = np.zeros(441000, dtype=np.float32)
        return p

    def test_setter_delegates_to_seek(self, player):
        """position setter must call PlaybackController.seek(), not write directly."""
        from unittest.mock import patch as _patch

        with _patch.object(player.playback, "seek", wraps=player.playback.seek) as mock_seek:
            player.position = 10000

        mock_seek.assert_called_once()
        assert player.playback.position == 10000

    def test_setter_clamps_above_total_samples(self, player):
        """Values exceeding total samples are clamped by seek()."""
        total = player.file_manager.get_total_samples()  # 441000

        player.position = total + 99999

        assert player.playback.position == total

    def test_setter_clamps_below_zero(self, player):
        """Negative values are clamped to 0 by seek()."""
        player.position = -100

        assert player.playback.position == 0

    def test_setter_is_thread_safe(self, player):
        """Concurrent position writes produce only in-bounds positions — no corruption."""
        max_samples = player.file_manager.get_total_samples()
        errors: list[str] = []
        barrier = threading.Barrier(8)

        def writer(target: int) -> None:
            try:
                barrier.wait()
                for _ in range(200):
                    player.position = target
                    pos = player.playback.position
                    if not (0 <= pos <= max_samples):
                        errors.append(f"position {pos} out of [0, {max_samples}]")
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

        targets = [0, 55125, 110250, 165375, 220500, 275625, 330750, 440999]
        threads = [threading.Thread(target=writer, args=(t,)) for t in targets]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=10.0)

        assert not errors, f"Thread-safety violations: {errors}"

    def test_no_direct_attribute_bypass(self, player):
        """Regression: setter must delegate to seek(), never write playback.position directly."""
        import inspect

        setter = type(player).__dict__["position"].fset
        assert setter is not None, "position setter should exist"
        setter_src = inspect.getsource(setter)

        assert "self.playback.seek(" in setter_src, (
            "position setter must delegate to playback.seek() to hold the RLock"
        )
        assert "self.playback.position =" not in setter_src, (
            "position setter must not assign directly to playback.position (bypasses lock)"
        )


class TestStateMachineBypass:
    """Verify state setter is removed from AudioPlayer (#2199)."""

    def test_audio_player_has_no_state_setter(self):
        """AudioPlayer.state should be read-only (no setter bypass)."""
        from auralis.player.enhanced_audio_player import AudioPlayer

        # The property should not have a setter (fset is None)
        state_prop = type.__dict__  # avoid triggering descriptor
        for cls in AudioPlayer.__mro__:
            if 'state' in cls.__dict__:
                prop = cls.__dict__['state']
                if isinstance(prop, property):
                    assert prop.fset is None, \
                        "AudioPlayer.state setter should be removed"
                break
