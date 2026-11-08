"""A ready prebuffer is used even when the next track has another sample rate (#6307).

#2408 made advance_with_prebuffer() throw a prebuffer away and decode the track
again whenever its rate differed from the current one, "to avoid a pitch/speed
error". The swap installs the buffer's own rate together with its audio, exactly
as the fallback decode does, so the guard prevented nothing and only turned a
gapless transition into a blocking decode.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest


def _install_current_track(fm, sr):
    with fm._audio_lock:
        fm.audio_data = np.zeros(1000, dtype=np.float32)
        fm.sample_rate = sr
        fm.current_file = "/current.wav"


def _prime_prebuffer(engine, next_track, audio, sr):
    with engine.update_lock:
        engine.next_track_buffer = audio
        engine.next_track_info = dict(next_track)
        engine.next_track_sample_rate = sr


@pytest.mark.parametrize(
    ("current_sr", "next_sr"),
    [(44100, 48000), (96000, 44100), (44100, 44100)],
    ids=["up", "down", "same"],
)
def test_the_prebuffer_is_swapped_in_with_its_own_rate_and_no_redecode(
    gapless_playback_engine, current_sr, next_sr
):
    engine = gapless_playback_engine
    fm = engine.file_manager
    _install_current_track(fm, current_sr)

    next_track = {"id": 7, "file_path": "/next.wav"}
    prebuffered = np.full(4096, 0.25, dtype=np.float32)
    _prime_prebuffer(engine, next_track, prebuffered, next_sr)

    engine.queue = MagicMock()
    engine.queue.peek_next_track.return_value = next_track
    engine.queue.advance_if_next_matches.return_value = True
    engine._load_track_audio = MagicMock(side_effect=AssertionError("decoded despite a ready prebuffer"))
    engine.start_prebuffering = MagicMock()

    assert engine.advance_with_prebuffer() is True

    engine._load_track_audio.assert_not_called()
    assert fm.audio_data is prebuffered
    assert fm.sample_rate == next_sr
    assert fm.current_file == "/next.wav"
    assert engine.next_track_buffer is None
