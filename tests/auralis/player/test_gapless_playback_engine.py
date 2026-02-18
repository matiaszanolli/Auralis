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
