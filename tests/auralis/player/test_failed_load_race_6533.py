"""A failed load racing a successful one never leaves the loaded player in ERROR (#6533).

_note_failed_load read is_loaded() under _audio_lock, released it, then called set_error().
A concurrent load that swapped in and ran load_and_stop in between had ERROR written over its
healthy STOPPED player, so play() was refused until another load succeeded. The test holds the
failed load just before set_error() until the good load finishes, or 0.5 s pass when the good
load is (correctly) waiting for the lock.
"""

import threading
from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf

from auralis.player.config import PlayerConfig
from auralis.player.enhanced_audio_player import AudioPlayer
from auralis.player.playback_controller import PlaybackState


@pytest.fixture
def files(tmp_path):
    good = tmp_path / "good.wav"
    sf.write(str(good), np.zeros((22050, 2), dtype="float32"), 22050)
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"this is not audio" * 50)
    return str(good), str(bad)


def test_a_good_load_finishing_inside_the_failed_loads_window_stays_playable(files, monkeypatch):
    good, bad = files
    player = AudioPlayer(config=PlayerConfig(), get_repository_factory=lambda: Mock())
    good_done = threading.Event()
    real_set_error = player.playback.set_error

    def set_error_after_the_good_load():
        good_done.wait(0.5)  # the old code was outside the lock here, so the good load ran meanwhile
        real_set_error()

    monkeypatch.setattr(player.playback, "set_error", set_error_after_the_good_load)

    failing = threading.Thread(target=player.load_file, args=(bad,))
    failing.start()
    threading.Event().wait(0.1)  # let the failed load reach set_error
    assert player.load_file(good) is True
    good_done.set()
    failing.join(10)

    assert player.playback.state != PlaybackState.ERROR
    assert player.play() is True
