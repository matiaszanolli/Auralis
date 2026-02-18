"""
Tests for GaplessPlaybackEngine

Covers:
- Deadlock regression: get_prebuffered_track() must not deadlock (#2197)
- Prebuffer lifecycle: store, retrieve, invalidate
- Thread lifecycle: single-thread invariant, clean shutdown, non-daemon (#2075)
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


# ============================================================================
# Position reset on gapless transition (issue #2283)
# ============================================================================

class TestGaplessTransitionPositionReset:
    """AudioPlayer.next_track() must reset position to 0 after any gapless advance.

    Before the fix, advance_with_prebuffer() set file_manager.audio_data for the
    new track but never called playback.stop() (which resets position).  Stale
    positions from the previous track caused get_audio_chunk() to read past the
    end of the new (often shorter) track, producing silence.

    The fix adds playback.seek(0, total_samples) in AudioPlayer.next_track()
    after advance_with_prebuffer() returns True, covering both the gapless
    (prebuffer) and fallback paths.
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

        # Load a "previous track" (441000 samples ≈ 10 s at 44.1 kHz)
        p.file_manager.audio_data = np.zeros(441000, dtype=np.float32)
        return p

    def _make_advance(self, player, new_samples: int = 882000):
        """Return a fake advance_with_prebuffer that installs new audio data."""
        import numpy as np

        def fake_advance(was_playing):
            player.file_manager.audio_data = np.zeros(new_samples, dtype=np.float32)
            return True

        return fake_advance

    def test_position_resets_to_zero_after_gapless_transition(self, player):
        """Stale end-of-track position is zeroed by next_track() (#2283)."""
        # Simulate player near the end of the previous track
        player.playback.seek(440000, 441000)
        assert player.playback.position == 440000

        player.gapless.advance_with_prebuffer.side_effect = self._make_advance(player)

        player.next_track()

        assert player.playback.position == 0, (
            f"Expected position=0 after gapless transition, got {player.playback.position}"
        )

    def test_position_resets_when_was_playing(self, player):
        """Position resets even when playback was active during the transition."""
        player.playback.play()
        player.playback.seek(400000, 441000)
        assert player.playback.is_playing()

        player.gapless.advance_with_prebuffer.side_effect = self._make_advance(player)

        player.next_track()

        assert player.playback.position == 0, (
            f"position={player.playback.position} after transition while playing"
        )

    def test_position_resets_when_was_paused(self, player):
        """Position resets even when player was paused at transition time."""
        player.playback.seek(300000, 441000)

        player.gapless.advance_with_prebuffer.side_effect = self._make_advance(player)

        player.next_track()

        assert player.playback.position == 0

    def test_position_unchanged_when_no_next_track(self, player):
        """If advance_with_prebuffer returns False, position must be preserved."""
        player.playback.seek(400000, 441000)
        player.gapless.advance_with_prebuffer.return_value = False

        player.next_track()

        assert player.playback.position == 400000

    def test_position_in_bounds_of_new_shorter_track(self, player):
        """Reset position is bounded to the new (shorter) track's sample count."""
        import numpy as np

        # Previous track is 441000 samples; new track is only 220500
        new_audio = np.zeros(220500, dtype=np.float32)

        def fake_advance(was_playing):
            player.file_manager.audio_data = new_audio
            return True

        player.playback.seek(440000, 441000)
        player.gapless.advance_with_prebuffer.side_effect = fake_advance

        player.next_track()

        assert player.playback.position == 0
        assert player.playback.position <= len(new_audio)

    def test_position_resets_on_sample_rate_change(self, player):
        """Stale position from 44.1kHz track must not bleed into 48kHz track (issue #2152).

        Without the fix, the position from the 44.1kHz track (e.g. 441000 samples)
        is carried over.  At 48kHz that maps to ~9.2s into the new track instead
        of 0s — producing a skip.  The fix (seek(0, total_samples) in next_track)
        covers this regardless of sample rate difference.
        """
        import numpy as np

        # Track A: 44.1kHz, 10s → 441000 samples; player is near the end
        player.file_manager.sample_rate = 44100
        player.playback.seek(440000, 441000)
        assert player.playback.position == 440000

        # Track B: 48kHz, 10s → 480000 samples
        new_audio = np.zeros(480000, dtype=np.float32)

        def fake_advance(was_playing):
            player.file_manager.audio_data = new_audio
            player.file_manager.sample_rate = 48000
            return True

        player.gapless.advance_with_prebuffer.side_effect = fake_advance

        player.next_track()

        assert player.playback.position == 0, (
            f"Expected position=0 after 44.1→48kHz transition, "
            f"got {player.playback.position} (~{player.playback.position / 48000:.2f}s into new track)"
        )
        assert player.file_manager.sample_rate == 48000


# ============================================================================
# Thread lifecycle and shutdown safety (issue #2075)
# ============================================================================

class TestPrebufferThreadLifecycle:
    """Prebuffer thread must not be killed mid-I/O on shutdown (issue #2075).

    Failures before the fix:
    - daemon=True: process exit kills thread while it holds an open file handle
    - TOCTOU race in start_prebuffering(): two concurrent callers both pass the
      is_alive() check and spawn duplicate threads
    - cleanup() didn't signal the worker, so join() always waited the full 2s

    Fixes:
    - daemon=False: thread runs to completion; process waits for it
    - _thread_lock around is_alive() + thread creation (atomic check-then-create)
    - _shutdown Event: worker exits at the next safe point; cleanup() sets it
      and joins with a 5s timeout
    """

    @pytest.fixture
    def slow_engine(self, audio_file_manager, queue_controller):
        """GaplessPlaybackEngine whose worker blocks until released by a test."""
        from unittest.mock import patch

        load_started = threading.Event()
        load_release = threading.Event()

        def slow_load(path, mode):
            load_started.set()
            load_release.wait(timeout=10.0)
            return np.zeros(44100, dtype=np.float32), 44100

        engine = GaplessPlaybackEngine(audio_file_manager, queue_controller)

        # Point queue at a fake track so the worker doesn't short-circuit
        queue_controller.add_track({"file_path": "/tmp/fake.wav"})

        engine._load_started = load_started
        engine._load_release = load_release
        engine._load_patch = patch("auralis.player.gapless_playback_engine.load", side_effect=slow_load)
        engine._load_patch.start()
        return engine

    def teardown_method(self, method):
        # Best-effort: nothing to tear down at class level
        pass

    # ------------------------------------------------------------------
    # Non-daemon
    # ------------------------------------------------------------------

    def test_prebuffer_thread_is_not_daemon(self, audio_file_manager, queue_controller):
        """Prebuffer thread must be daemon=False so it isn't killed mid-I/O (#2075)."""
        from unittest.mock import patch

        load_barrier = threading.Barrier(2)

        def controlled_load(path, mode):
            load_barrier.wait(timeout=5.0)   # sync with test
            load_barrier.wait(timeout=5.0)   # hold until released
            return np.zeros(44100, dtype=np.float32), 44100

        engine = GaplessPlaybackEngine(audio_file_manager, queue_controller)
        queue_controller.add_track({"file_path": "/tmp/fake.wav"})

        with patch("auralis.player.gapless_playback_engine.load", side_effect=controlled_load):
            engine.start_prebuffering()
            load_barrier.wait(timeout=5.0)   # wait until worker is in load()

            assert engine.prebuffer_thread is not None
            assert engine.prebuffer_thread.daemon is False, (
                "Prebuffer thread must be daemon=False to prevent mid-I/O termination"
            )

            load_barrier.wait(timeout=5.0)   # release the load
            engine.prebuffer_thread.join(timeout=5.0)

    # ------------------------------------------------------------------
    # Single-thread invariant
    # ------------------------------------------------------------------

    def test_single_thread_under_concurrent_calls(self, audio_file_manager, queue_controller):
        """Concurrent start_prebuffering() calls must spawn at most one thread (#2075)."""
        from unittest.mock import patch

        threads_created: list[int] = []
        load_gate = threading.Event()

        def gated_load(path, mode):
            with threading.Lock():
                threads_created.append(threading.current_thread().ident)
            load_gate.wait(timeout=5.0)
            return np.zeros(44100, dtype=np.float32), 44100

        engine = GaplessPlaybackEngine(audio_file_manager, queue_controller)
        queue_controller.add_track({"file_path": "/tmp/fake.wav"})

        with patch("auralis.player.gapless_playback_engine.load", side_effect=gated_load):
            # Fire 10 concurrent calls to start_prebuffering
            callers = [
                threading.Thread(target=engine.start_prebuffering)
                for _ in range(10)
            ]
            for t in callers:
                t.start()
            for t in callers:
                t.join(timeout=5.0)

            load_gate.set()   # let the worker (if any) finish
            if engine.prebuffer_thread:
                engine.prebuffer_thread.join(timeout=5.0)

        assert len(threads_created) <= 1, (
            f"Expected at most 1 prebuffer thread, but {len(threads_created)} were spawned"
        )

    # ------------------------------------------------------------------
    # Clean shutdown via _shutdown event
    # ------------------------------------------------------------------

    def test_cleanup_joins_running_thread(self, slow_engine):
        """cleanup() must join the prebuffer thread within the timeout (#2075)."""
        engine = slow_engine

        engine.start_prebuffering()
        engine._load_started.wait(timeout=5.0)  # thread is now inside load()

        # Release the load so cleanup() can finish promptly
        engine._load_release.set()
        engine.cleanup()

        assert engine.prebuffer_thread is None or not engine.prebuffer_thread.is_alive(), (
            "Prebuffer thread must have stopped after cleanup()"
        )
        engine._load_patch.stop()

    def test_shutdown_prevents_new_thread_after_cleanup(self, audio_file_manager, queue_controller):
        """start_prebuffering() is a no-op after cleanup() has been called (#2075)."""
        engine = GaplessPlaybackEngine(audio_file_manager, queue_controller)
        engine.cleanup()   # sets _shutdown

        engine.start_prebuffering()

        assert engine.prebuffer_thread is None or not engine.prebuffer_thread.is_alive(), (
            "No new thread should start after cleanup() has been called"
        )

    def test_worker_skips_load_after_shutdown_set(self, audio_file_manager, queue_controller):
        """Worker must exit without calling load() when _shutdown is set before it runs (#2075)."""
        from unittest.mock import patch

        load_called = threading.Event()

        def detecting_load(path, mode):
            load_called.set()
            return np.zeros(44100, dtype=np.float32), 44100

        engine = GaplessPlaybackEngine(audio_file_manager, queue_controller)
        queue_controller.add_track({"file_path": "/tmp/fake.wav"})
        engine._shutdown.set()   # signal shutdown before starting

        with patch("auralis.player.gapless_playback_engine.load", side_effect=detecting_load):
            engine.start_prebuffering()   # no-op because _shutdown is set

        assert not load_called.is_set(), (
            "load() must not be called when _shutdown is set before start_prebuffering()"
        )
