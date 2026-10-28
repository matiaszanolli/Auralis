"""An advance whose decode outlives cleanup() commits nothing (#6127)

#3727 checked ``_cleanup_in_progress`` once, at the top of ``_auto_advance_next``. A thread
already inside ``advance_with_prebuffer`` (a blocking decode, no lock held) never looked again, so
after cleanup()'s join timed out and ``clear_all()`` ran, the advance committed the queue and
installed the decoded track into the cleaned player. ``abort`` is polled after the decode, before
the commit.
"""

from unittest.mock import MagicMock

import numpy as np


def _engine_with_unprimed_prebuffer(gapless_playback_engine):
    engine = gapless_playback_engine
    engine.queue = MagicMock()
    engine.queue.peek_next_track.return_value = {"id": 2, "file_path": "/next.wav"}
    engine.queue.advance_if_next_matches.return_value = True
    engine._load_track_audio = MagicMock(return_value=(np.zeros(2048, dtype=np.float32), 44100))
    return engine


def test_abort_raised_during_the_decode_commits_nothing(gapless_playback_engine):
    engine = _engine_with_unprimed_prebuffer(gapless_playback_engine)
    cleanup_started = False

    def decode_while_cleanup_runs(path):
        nonlocal cleanup_started
        cleanup_started = True  # cleanup() lands while the decode is in flight
        return np.zeros(2048, dtype=np.float32), 44100

    engine._load_track_audio.side_effect = decode_while_cleanup_runs

    advanced = engine.advance_with_prebuffer(abort=lambda: cleanup_started)

    assert advanced is False
    engine.queue.advance_if_next_matches.assert_not_called()
    assert engine.file_manager.audio_data is None


def test_without_an_abort_the_advance_still_commits_and_installs(gapless_playback_engine):
    engine = _engine_with_unprimed_prebuffer(gapless_playback_engine)

    advanced = engine.advance_with_prebuffer(abort=lambda: False)

    assert advanced is True
    engine.queue.advance_if_next_matches.assert_called_once()
    assert engine.file_manager.current_file == "/next.wav"
