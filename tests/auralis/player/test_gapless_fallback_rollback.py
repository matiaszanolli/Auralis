"""
Regression test: gapless fallback abort restores audio state (#4100)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

advance_with_prebuffer()'s fallback path calls file_manager.load_file() — which
atomically swaps audio_data/sample_rate/current_file — and only then re-checks
queue.advance_if_next_matches(). If a second concurrent mutation fails that
re-check, the method returned False with audio_data already on the new track
while current_index still pointed at the old one (the caller only resets
position / reloads the fingerprint on True). The abort now rolls the swap back.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from unittest.mock import MagicMock

import numpy as np


def _prime_prebuffer(engine, next_track, sr):
    with engine.update_lock:
        engine.next_track_buffer = np.zeros(2048, dtype=np.float32)
        engine.next_track_info = dict(next_track)
        engine.next_track_sample_rate = sr


def test_fallback_double_mutation_restores_prior_track(gapless_playback_engine):
    engine = gapless_playback_engine
    fm = engine.file_manager

    # Pre-fallback ("old") track state.
    old_audio = np.full(1000, 0.1, dtype=np.float32)
    with fm._audio_lock:
        fm.audio_data = old_audio
        fm.sample_rate = 44100
        fm.current_file = "/old.wav"

    next_track = {"id": 1, "file_path": "/next.wav"}
    fresh_next = {"id": 2, "file_path": "/fresh.wav"}
    # Prebuffer matches next_track AND its sample rate matches current playback,
    # so we reach the commit path.
    _prime_prebuffer(engine, next_track, sr=44100)

    engine.queue = MagicMock()
    # peek: first the prebuffered next_track, then the fresh next after mutation.
    engine.queue.peek_next_track.side_effect = [next_track, fresh_next]
    # Both advance attempts lose the race (first → fallback, second → abort).
    engine.queue.advance_if_next_matches.return_value = False

    # load_file swaps to the "new" track (as the real one does) and succeeds.
    new_audio = np.full(3000, 0.9, dtype=np.float32)

    def fake_load(path):
        with fm._audio_lock:
            fm.audio_data = new_audio
            fm.sample_rate = 48000
            fm.current_file = path
        return True

    fm.load_file = MagicMock(side_effect=fake_load)
    engine.start_prebuffering = MagicMock()  # should not be reached

    result = engine.advance_with_prebuffer(was_playing=True)

    assert result is False
    # The swap was rolled back: audio_data matches the un-advanced index again.
    assert fm.audio_data is old_audio
    assert fm.sample_rate == 44100
    assert fm.current_file == "/old.wav"
    engine.start_prebuffering.assert_not_called()


def test_fallback_success_keeps_new_track(gapless_playback_engine):
    """Control: when the fallback advance succeeds, the new track is kept."""
    engine = gapless_playback_engine
    fm = engine.file_manager

    old_audio = np.full(1000, 0.1, dtype=np.float32)
    with fm._audio_lock:
        fm.audio_data = old_audio
        fm.sample_rate = 44100
        fm.current_file = "/old.wav"

    next_track = {"id": 1, "file_path": "/next.wav"}
    fresh_next = {"id": 2, "file_path": "/fresh.wav"}
    _prime_prebuffer(engine, next_track, sr=44100)

    engine.queue = MagicMock()
    engine.queue.peek_next_track.side_effect = [next_track, fresh_next]
    # First advance fails (→ fallback); second succeeds (→ commit).
    engine.queue.advance_if_next_matches.side_effect = [False, True]

    new_audio = np.full(3000, 0.9, dtype=np.float32)

    def fake_load(path):
        with fm._audio_lock:
            fm.audio_data = new_audio
            fm.sample_rate = 48000
            fm.current_file = path
        return True

    fm.load_file = MagicMock(side_effect=fake_load)
    engine.start_prebuffering = MagicMock()

    result = engine.advance_with_prebuffer(was_playing=True)

    assert result is True
    assert fm.audio_data is new_audio
    assert fm.current_file == "/fresh.wav"
    engine.start_prebuffering.assert_called_once()
